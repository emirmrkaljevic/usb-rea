# usb-rea — Reverse Engineer any USB gadget

[![ci](https://github.com/emirmrkaljevic/usb-rea/actions/workflows/ci.yml/badge.svg)](https://github.com/emirmrkaljevic/usb-rea/actions/workflows/ci.yml) ![license](https://img.shields.io/badge/license-MIT-blue)

![usb-rea demo: capture labelled clicks, get the protocol and a working driver](docs/demo.gif)

Got a USB device that only ships a Windows vendor app (case LCD, RGB controller, mouse, "smart" lamp)? Click around in the vendor app while **usb-rea** captures the USB traffic (usbmon on Linux, USBPcap on Windows), diffs the packets per action, infers the protocol, and writes an open-source Python/libusb driver — with every conclusion linked to the exact packets that prove it.

> Status: alpha (v0.1.0). Validated on synthetic devices, on protocols documented by liquidctl and rivalcfg, and on public Wireshark captures — see [docs/VALIDATION.md](docs/VALIDATION.md). Not yet tested on a physical gadget: your captures are welcome.

## Try it in 10 seconds (no hardware needed)
```bash
pip install git+https://github.com/emirmrkaljevic/usb-rea
usb-rea demo --device fan
```
```
fan    100%  0x5a | counter (+1 per message) | 0x10 | u16be round(value * 1 + 0) | 0x00 | u16le crc16_modbus(bytes[0:6])
color  100%  0x5a | counter (+1 per message) | 0x20 | round(value * 1 + 0) | round(value[1] * 1 + 0) | round(value[2] * 1 + 0) | u16le crc16_modbus(bytes[0:6])
mode   100%  0x5a | counter (+1 per message) | 0x30 | lookup 1→0x11, 2→0x22, 3→0x47 | 0x00 | 0x00 | u16le crc16_modbus(bytes[0:6])
```
It writes a synthetic capture of a fan controller, recovers the protocol, and writes `report.md` (every claim linked to Wireshark frame numbers) and a working pyusb driver that encodes values it never saw.

## What it can infer
| Role | Example |
|---|---|
| constant header / command id | `5a`, `10` vs `20` vs `30` |
| linear values, 8- or 16-bit LE/BE, several per action | `fan 2650` → `0a 5a`; `color 255 24 0` |
| lookup tables (non-linear choices) | DPI 250→`08`, 500→`07` … |
| rolling counters | sequence byte +1 per message |
| checksums | sum8, xor8, neg/inv sum8, sum16, CRC8, CRC8/MAXIM, CRC16 CCITT-FALSE/XMODEM/MODBUS/KERMIT |

Linear fits must survive leave-one-out cross-checks; otherwise usb-rea falls back to an honest lookup table and says so.

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
- [x] checksum detection (sum8, xor8, neg/inv sum8, CRC8, CRC16 variants)
- [x] evidence-backed protocol report
- [x] driver scaffolding (pyusb, bulk/interrupt + control/HID SET_REPORT)
- [x] confirmed replay
- [x] MCP server
- [x] rolling counters, multi-byte (16-bit LE/BE) values, lookup tables, multi-value actions
- [x] validation against documented protocols (liquidctl, rivalcfg)
- [ ] emulated-device CI (dummy_hcd + configfs HID; script in `scripts/gadget_e2e.sh`)
- [ ] real-hardware case studies
- [ ] state machines / multi-packet transactions, 32-bit values, bitfields
- [ ] HID report descriptor decoding

## Legal
Reverse engineering for interoperability is permitted (EU Directive 2009/24/EC Art. 6, US DMCA §1201(f)). usb-rea only analyzes traffic of devices you own and never redistributes vendor code.

## License
MIT
