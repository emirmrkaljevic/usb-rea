# usb-rea — Reverse Engineer any USB gadget

<!-- mcp-name: io.github.emirmrkaljevic/usb-rea -->

[![ci](https://github.com/emirmrkaljevic/usb-rea/actions/workflows/ci.yml/badge.svg)](https://github.com/emirmrkaljevic/usb-rea/actions/workflows/ci.yml) ![license](https://img.shields.io/badge/license-MIT-blue) [![usb-rea MCP server](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea/badges/score.svg)](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea)

![usb-rea demo: capture labelled clicks, get the protocol and a working driver](docs/demo.gif)

Got a USB device that only ships a Windows vendor app (case LCD, RGB controller, mouse, "smart" lamp)? Click around in the vendor app while **usb-rea** captures the USB traffic (usbmon on Linux, USBPcap on Windows), diffs the packets per action, infers the protocol, and writes an open-source Python/libusb driver — with every conclusion linked to the exact packets that prove it.

> Status: alpha (v0.2.1, [on PyPI](https://pypi.org/project/usb-rea/)). Validated on synthetic devices, on protocols documented by liquidctl and rivalcfg, and on public Wireshark captures — see [docs/VALIDATION.md](docs/VALIDATION.md). Not yet tested on a physical gadget: your captures are welcome.

## Try it in 10 seconds (no hardware needed)
```bash
pip install usb-rea
usb-rea demo --device fan
```
```
fan    100%  0x5a | counter (+1 per message) | 0x10 | u16be round(value * 1 + 0) | 0x00 | u16le crc16_modbus(bytes[0:6])
color  100%  0x5a | counter (+1 per message) | 0x20 | round(value * 1 + 0) | round(value[1] * 1 + 0) | round(value[2] * 1 + 0) | u16le crc16_modbus(bytes[0:6])
mode   100%  0x5a | counter (+1 per message) | 0x30 | lookup 1→0x11, 2→0x22, 3→0x47 | 0x00 | 0x00 | u16le crc16_modbus(bytes[0:6])
```
It writes a synthetic capture of a fan controller, recovers the protocol, and writes `report.md` (every claim linked to Wireshark frame numbers) and a working pyusb driver that encodes values it never saw.

`--device lamp` (default) is a simple 8-bit device; `--device dial` shows 32-bit values and packed bitfields:
```
position     100%  0xa5 | 0x01 | u32le round(value * 1 + 0) | sum8(bytes[0:6])
level        100%  0xa5 | 0x02 | bits[0:4] = round(value * 1 + 0) | 0x00 | sum8(bytes[0:4])
```

## What it can infer
| Role | Example |
|---|---|
| constant header / command id | `5a`, `10` vs `20` vs `30` |
| linear values, 8-, 16- or 32-bit LE/BE, several per action | `fan 2650` → `0a 5a`; `color 255 24 0`; `position 50000` → `50 c3 00 00` |
| packed bitfields (bits beside constant flag bits, incl. 12-bit spans over two bytes) | `level 7` → `b7` = flags `b0` + bits[0:4] |
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
usb-rea dissector lamp.pcapng -o lamp.lua      # Wireshark dissector for the same protocol
```
Captured on Windows with USBPcap/Wireshark and no markers? Click each action with a short pause in between, then just list them in order — usb-rea splits the traffic at the pauses:
```bash
usb-rea report lamp.pcapng --labels "brightness 0%; brightness 50%; brightness 100%; power off; power on"
usb-rea scaffold lamp.pcapng --labels labels.txt -o lamp_driver.py   # one label per line
```
(Markers, if you have them, are a JSON list of `{"label", "start", "end"}` epoch timestamps.)

Most vendor apps also poll the device on their own (a "get status" every few hundred ms, keep-alives).
usb-rea spots identical host→device messages sent on a steady rhythm, away from your clicks, and sets
them aside before splitting and diffing; the report lists them under *Background traffic (ignored)*
with their period and frame numbers. A constant "apply" packet that always follows a real command is
not treated as background. Polls whose bytes change every time (e.g. with a sequence number) are not
detected yet.

## MCP server
`pip install usb-rea` then add `usb-rea mcp` as a stdio server. Tools: `capture_start`, `capture_stop`, `mark_action`, `diff_actions`, `report`, `scaffold_driver`, `hid_descriptor` (decode a HID report descriptor / report payloads), `wireshark_dissector`, `replay_packet` (refuses unless the human confirmed). Analysis tools accept the same `labels` argument as the CLI for marker-free captures.

With [uv](https://docs.astral.sh/uv/) no install step is needed:
```json
{"mcpServers": {"usb-rea": {"command": "uvx", "args": ["--from", "usb-rea", "usb-rea", "mcp"]}}}
```
For Claude Code: `claude mcp add usb-rea -- uvx --from usb-rea usb-rea mcp`. The server is also listed on the [official MCP Registry](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.emirmrkaljevic/usb-rea) as `io.github.emirmrkaljevic/usb-rea` and on [Glama](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea), which builds it from the repo's `Dockerfile` and checks that it starts and lists its tools.

## How it works
1. `usb-rea capture start` — record traffic (usbmon / USBPcap)
2. `usb-rea mark "brightness 50%"` — label each action you take in the vendor app
3. `usb-rea diff` — which bytes change per action, value correlation, checksums, counters
4. `usb-rea infer` — message templates + evidence report
5. `usb-rea scaffold` — generate a pyusb driver and replay tests
6. `usb-rea dissector` — write a Wireshark Lua dissector for the inferred protocol
7. `usb-rea replay` — send packets to the device (only with explicit confirmation)
8. `usb-rea hid` — decode a HID report descriptor from a capture (GET_DESCRIPTOR 0x22) or from hex, and decode report payloads
9. `usb-rea mcp` — the same tools as an MCP server for AI agents

### Wireshark dissector
`usb-rea dissector capture.pcapng -o lamp.lua` turns the inferred protocol into a Wireshark Lua plugin, so you can keep
capturing and read the traffic as commands instead of hex:
```bash
wireshark -X lua_script:lamp.lua capture.pcapng
tshark -X lua_script:lamp.lua -r capture.pcapng -Y 'usbrea.command == "brightness"'
```
Each matching packet gets a `usbrea` tree with the command name, decoded values (`usbrea.brightness.value`), counters,
lookup labels, and a checksum check (`usbrea.checksum_ok`, with an expert warning on mismatch); the Info column reads
`brightness 50`. It works for bulk, interrupt and control/HID SET_REPORT transfers, from usbmon or USBPcap, and needs no
bit library (Wireshark 3.x and 4.x). `-n NAME` changes the filter prefix. CI runs every generated dissector through tshark.

### HID devices
Most RGB keyboards, mice, headsets and LCD gadgets are HID with a vendor-defined page. If the capture includes the
report descriptor (start capturing, then replug the device), the report gets a section with every report's ID, size and
fields, and each inferred command is tagged with the HID report it travels in. Without a capture:

```sh
usb-rea hid /sys/class/hidraw/hidraw0/device/report_descriptor --items
usb-rea hid capture.pcapng --decode "10ff0d1d000000" --type Output
```

## Roadmap
- [x] pcap/pcapng parser (usbmon + USBPcap)
- [x] action markers and per-action diffing
- [x] checksum detection (sum8, xor8, neg/inv sum8, CRC8, CRC16 variants)
- [x] evidence-backed protocol report
- [x] driver scaffolding (pyusb, bulk/interrupt + control/HID SET_REPORT)
- [x] confirmed replay
- [x] MCP server
- [x] rolling counters, multi-byte (16/32-bit LE/BE) values, lookup tables, multi-value actions
- [x] packed bitfields
- [x] validation against documented protocols (liquidctl, rivalcfg)
- [x] HID report descriptor decoding (`usb-rea hid`), with captured commands mapped to their HID reports
- [ ] emulated-device CI (dummy_hcd + configfs HID; script in `scripts/gadget_e2e.sh`)
- [ ] real-hardware case studies
- [x] multi-packet transactions (write + apply), including checksums over earlier packets
- [x] background traffic: periodic status polls / keep-alives are detected and ignored
- [ ] state machines (request/response handshakes)

## Legal
Reverse engineering for interoperability is permitted (EU Directive 2009/24/EC Art. 6, US DMCA §1201(f)). usb-rea only analyzes traffic of devices you own and never redistributes vendor code.

## Support my work

[![Get a SkinToScan pack](https://img.shields.io/badge/%E2%98%95_Support_me-Get_a_SkinToScan_pack-ff5f5f?style=for-the-badge)](https://skintoscan.com/#packages)

If you find this useful, you can support me by getting a SkinToScan pack, my other project. It's a one-time purchase that directly funds my open-source work.

## License
MIT
