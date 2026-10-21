# Public USB captures used in tests

These files are **not** stored in this repository (their redistribution terms are not stated), so
`tests/test_public_pcaps.py` downloads them on demand into `~/.cache/usb-rea/pcaps/`, verifies the
sha256, and skips if offline.

| File | Source | Link type | What we check |
|---|---|---|---|
| `usb_memory_stick.pcap` | Wireshark SampleCaptures, "USB with Linux encapsulation (DLT 189)", https://wiki.wireshark.org/SampleCaptures | 189 usbmon | VID:PID from GET_DESCRIPTOR; every bulk OUT is a Mass Storage CBW (`USBC`), bulk IN status is CSW (`USBS`) |
| `usb_u3v_sample.pcapng` | Wireshark SampleCaptures, "USB with USBPcap encapsulation", same page | 249 USBPcap | VID:PID; every bulk OUT command starts with the USB3 Vision prefix `U3VC` |
