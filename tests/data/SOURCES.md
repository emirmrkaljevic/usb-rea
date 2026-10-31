# Public USB captures used in tests

These files are **not** stored in this repository (their redistribution terms are not stated), so
`tests/test_public_pcaps.py` downloads them on demand into `~/.cache/usb-rea/pcaps/`, verifies the
sha256, and skips if offline.

| File | Source | Link type | What we check |
|---|---|---|---|
| `usb_memory_stick.pcap` | Wireshark SampleCaptures, "USB with Linux encapsulation (DLT 189)", https://wiki.wireshark.org/SampleCaptures | 189 usbmon | VID:PID from GET_DESCRIPTOR; every bulk OUT is a Mass Storage CBW (`USBC`), bulk IN status is CSW (`USBS`) |
| `usb_u3v_sample.pcapng` | Wireshark SampleCaptures, "USB with USBPcap encapsulation", same page | 249 USBPcap | VID:PID; every bulk OUT command starts with the USB3 Vision prefix `U3VC` |

## Stored here

| File | Source | Link type | What we check |
|---|---|---|---|
| `asus-tuf-lc3-lcd.pcap.gz` | A real capture of an ASUS TUF Gaming LC III AIO with LCD (0B05:1C7B) under the vendor app on Windows, shared by its owner in [liquidctl#936](https://github.com/liquidctl/liquidctl/issues/936), who agreed to a trimmed copy being kept as a test | 249 USBPcap | VID:PID from the GET_DESCRIPTOR reply in USBPcap's "complete" record; brightness command on EP 0x01 (byte 4); 320x320 JPEG stream on EP 0x03 with `08 nn 00 80` / `08 ii 00 00` headers |

The stored copy keeps only this device's packets: the setup, the first 8 frames and two frames on
each side of the 4 brightness changes (589 packets). The JPEG headers stay, but the image data in
every frame is zeroed (only the end marker is kept), so nothing shown on the screen is in the file.
Timestamps are shifted to start at a fixed date and IRP ids are replaced with counters.
