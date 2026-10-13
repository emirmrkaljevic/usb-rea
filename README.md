# usb-rea — Reverse Engineer any USB gadget

Got a USB device that only ships a Windows vendor app (case LCD, RGB controller, mouse, "smart" lamp)? Click around in the vendor app while **usb-rea** captures the USB traffic (usbmon on Linux, USBPcap on Windows), diffs the packets per action, infers the protocol, and writes an open-source Python/libusb driver — with every conclusion linked to the exact packets that prove it.

> Status: pre-alpha, under active development.

## How it works
1. `usb-rea capture start` — record traffic (usbmon / USBPcap)
2. `usb-rea mark "brightness 50%"` — label each action you take in the vendor app
3. `usb-rea diff` — which bytes change per action, value correlation, checksums, counters
4. `usb-rea infer` — message templates + evidence report
5. `usb-rea scaffold` — generate a pyusb driver and replay tests
6. `usb-rea replay` — send packets to the device (only with explicit confirmation)
7. `usb-rea mcp` — the same tools as an MCP server for AI agents

## Roadmap
- [ ] pcap/pcapng parser (usbmon + USBPcap)
- [ ] action markers and per-action diffing
- [ ] checksum / counter detection
- [ ] evidence-backed protocol report
- [ ] driver scaffolding (pyusb)
- [ ] confirmed replay
- [ ] MCP server
- [ ] HID report descriptor decoding

## Legal
Reverse engineering for interoperability is permitted (EU Directive 2009/24/EC Art. 6, US DMCA §1201(f)). usb-rea only analyzes traffic of devices you own and never redistributes vendor code.

## License
MIT
