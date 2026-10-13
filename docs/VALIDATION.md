# Validation

usb-rea is validated without anyone's hardware in four ways. All of them run in CI (`pytest`).

| Suite | What it proves | File |
|---|---|---|
| Synthetic lamp | constant header, command byte, scaled value, sum8, over bulk and HID SET_REPORT | `tests/test_infer.py` |
| Synthetic fan controller | rolling counter, 16-bit big-endian value, 3-value RGB, lookup table, CRC16/MODBUS | `tests/test_infer_advanced.py` |
| liquidctl Kraken X (1e71:170e) | recovers `02 4d <channel> 00 <duty>` exactly as liquidctl's `kraken2.py` builds it | `tests/test_validation.py` |
| rivalcfg Rival 100 (1038:1702) | recovers non-linear DPI/polling lookup tables and RGB color as in rivalcfg's `rival100.py` | `tests/test_validation.py` |
| CRC catalogue | CRC8/CRC16 variants match the standard `123456789` check values | `tests/test_checksums.py` |
| Real captures | parser handles public usbmon/USBPcap captures (downloaded on demand) | `tests/test_public_pcaps.py` |

The driver generated from each capture is also executed against a mocked pyusb device and must emit
byte-identical packets for values that were **never captured**.

## Not yet covered
* Emulated USB gadget (dummy_hcd + raw-gadget). It needs a kernel with `CONFIG_USB_DUMMY_HCD` and
  `CONFIG_USB_RAW_GADGET`; the development box runs a sandboxed kernel without them. Script planned in
  `scripts/gadget_e2e.sh` for anyone with a normal Linux machine.
* Real hardware. Captures + action labels from users are very welcome (open an issue).
