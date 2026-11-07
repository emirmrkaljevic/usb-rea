# Validation

usb-rea is validated without anyone's hardware in four ways. All of them run in CI (`pytest`).

| Suite | What it proves | File |
|---|---|---|
| Synthetic lamp | constant header, command byte, scaled value, sum8, over bulk and HID SET_REPORT | `tests/test_infer.py` |
| Synthetic fan controller | rolling counter, 16-bit big-endian value, 3-value RGB, lookup table, CRC16/MODBUS | `tests/test_infer_advanced.py` |
| liquidctl Kraken X (1e71:170e) | recovers `02 4d <channel> 00 <duty>` exactly as liquidctl's `kraken2.py` builds it | `tests/test_validation.py` |
| rivalcfg Rival 100 (1038:1702) | recovers non-linear DPI/polling lookup tables and RGB color as in rivalcfg's `rival100.py` | `tests/test_validation.py` |
| liquidctl Hydro H100i Platinum (1b1c:0c18) | recovers prefix, sequence counter (+8), duty scale, pump mode and CRC8 as in `hydro_platinum.py`; [case study](case-study-hydro-platinum.md) | `tests/test_case_hydro_platinum.py` |
| ASUS TUF Gaming LC III LCD (0b05:1c7b) | real USBPcap capture: brightness on EP 0x01 (byte 4 = percent), 320x320 JPEG stream on EP 0x03 with `08 nn 00 80` / `08 ii 00 00`, ack `08 81` on EP 0x84, VID:PID from USBPcap stage-3 GET_DESCRIPTOR; [case study](case-study-asus-tuf-lc3.md) | `tests/test_user_capture_lc3.py` |
| CRC catalogue | CRC8/CRC16 variants match the standard `123456789` check values | `tests/test_checksums.py` |
| Wireshark dissector | generated Lua plugin labels every command in tshark 4.4, values match, checksums verify, a corrupted checksum is flagged; Lua checksum helpers match the Python ones | `tests/test_dissector.py` |
| Real captures | parser handles public usbmon/USBPcap captures (downloaded on demand) | `tests/test_public_pcaps.py` |

The driver generated from each capture is also executed against a mocked pyusb device and must emit
byte-identical packets for values that were **never captured**.

## Emulated USB gadget (local only)
`scripts/gadget_e2e.sh` turns the machine into its own USB device: it creates a vendor-defined HID "lamp" on
`dummy_hcd` through configfs, captures the real kernel traffic with usbmon while writing lamp commands to the
hidraw node, runs usb-rea on the capture and checks that the inferred brightness and hue commands encode exactly
like the reference encoder, including values that were never written.

It needs a kernel with `CONFIG_USB_DUMMY_HCD`, `CONFIG_USB_LIBCOMPOSITE`, `CONFIG_USB_CONFIGFS_F_HID` and
`CONFIG_USB_MON`, plus root. That is why it is not in CI: the GitHub hosted runner kernel has no `dummy_hcd`, and
Ubuntu's generic kernel is built without it too (`# CONFIG_USB_DUMMY_HCD is not set`), so booting it in a VM does
not help. Arch, Fedora or a self-built kernel usually work. To run it:

```sh
zgrep DUMMY_HCD /proc/config.gz 2>/dev/null || grep DUMMY_HCD /boot/config-$(uname -r)   # want =m or =y
sudo apt install tshark            # or your distro's wireshark-cli, for dumpcap
pip install -e .
sudo env "PATH=$PATH" bash scripts/gadget_e2e.sh
```

It prints `gadget e2e OK` and the temp directory with the capture and report, and removes the gadget on exit.

## Not yet covered
* Emulated USB gadget in CI (see above, needs a runner kernel with `dummy_hcd`).
* Real hardware. Captures + action labels from users are very welcome (open an issue).
