# usb-rea — Reverse Engineer any USB gadget

Got a USB device that only ships a Windows vendor app (case LCD, RGB controller, mouse, "smart" lamp)? Click around in the vendor app while **usb-rea** captures the USB traffic (usbmon on Linux, USBPcap on Windows), diffs the packets per action, infers the protocol, and writes an open-source Python/libusb driver — with every conclusion linked to the exact packets that prove it.

> Status: alpha. The full pipeline works end-to-end on synthetic captures; real-device validation in progress.

## Try it in 10 seconds (no hardware needed)
```bash
pip install git+https://github.com/emirmrkaljevic/usb-rea
usb-rea demo
```
```
brightness   100%  0xaa 0x01 round(value * 2.55 + 0) 0x00 sum8(bytes[0:4])
power         60%  0xaa 0x02 round(value * 1 + 0) 0x00 sum8(bytes[0:4])
hue          100%  0xaa 0x03 round(value * 0.5 + 0) 0x00 sum8(bytes[0:4])
```
It writes a fake lamp capture, recovers the protocol (constant header, command byte, value scaling, sum8 checksum), and writes `report.md` (every claim linked to Wireshark frame numbers) and a working pyusb driver.

## Real device workflow (Linux)
```bash
sudo modprobe usbmon
usb-rea capture start -o lamp.pcapng
usb-rea mark -m lamp.pcapng.actions.json "brightness 0%"    # then click it in the vendor app
usb-rea mark -m lamp.pcapng.actions.json "brightness 50%"   # ...repeat for 3+ values per setting
usb-rea capture stop
usb-rea report lamp.pcapng -o report.md
usb-rea scaffold lamp.pcapng -o lamp_driver.py
```
Captured on Windows with USBPcap/Wireshark? Pass the `.pcapng` directly; markers are a JSON list of `{"label", "start", "end"}` epoch timestamps.

## MCP server
`pip install "usb-rea[mcp]"` then add `usb-rea mcp` as a stdio server. Tools: `capture_start`, `capture_stop`, `mark_action`, `diff_actions`, `report`, `scaffold_driver`, `replay_packet` (refuses unless the human confirmed).

## How it works
1. `usb-rea capture start` — record traffic (usbmon / USBPcap)
2. `usb-rea mark "brightness 50%"` — label each action you take in the vendor app
3. `usb-rea diff` — which bytes change per action, value correlation, checksums, counters
4. `usb-rea infer` — message templates + evidence report
5. `usb-rea scaffold` — generate a pyusb driver and replay tests
6. `usb-rea replay` — send packets to the device (only with explicit confirmation)
7. `usb-rea mcp` — the same tools as an MCP server for AI agents

## Roadmap
- [x] pcap/pcapng parser (usbmon + USBPcap)
- [x] action markers and per-action diffing
- [x] checksum detection (sum8, xor8, neg/inv sum8)
- [x] evidence-backed protocol report
- [x] driver scaffolding (pyusb, bulk/interrupt + control/HID SET_REPORT)
- [x] confirmed replay
- [x] MCP server
- [ ] rolling counters, CRC8/CRC16, multi-byte (16-bit LE/BE) values
- [ ] emulated-device CI (dummy_hcd + raw-gadget)
- [ ] validation against documented protocols (liquidctl, rivalcfg, HID++)
- [ ] HID report descriptor decoding

## Legal
Reverse engineering for interoperability is permitted (EU Directive 2009/24/EC Art. 6, US DMCA §1201(f)). usb-rea only analyzes traffic of devices you own and never redistributes vendor code.

## License
MIT
