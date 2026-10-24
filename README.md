# usb-rea: Reverse Engineer any USB gadget

<!-- mcp-name: io.github.emirmrkaljevic/usb-rea -->

[![ci](https://github.com/emirmrkaljevic/usb-rea/actions/workflows/ci.yml/badge.svg)](https://github.com/emirmrkaljevic/usb-rea/actions/workflows/ci.yml) ![license](https://img.shields.io/badge/license-MIT-blue) [![usb-rea MCP server](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea/badges/score.svg)](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea)

<p align="center"><a href="https://skintoscan.com/#packages"><img src=".github/assets/skintoscan-support.svg" width="684" alt="Support my open-source work: get a SkinToScan pack"></a><br><sub>If you find this useful, you can support me by getting a SkinToScan pack, my other project. It's a one-time purchase that directly funds my open-source work.</sub></p>
<p align="center"><a href="https://skintoscan.com/checkout/?add-to-cart=138"><img src=".github/assets/skintoscan-pack-1.svg" width="220" alt="Buy Single Picture Check, €4.49"></a> <a href="https://skintoscan.com/checkout/?add-to-cart=139"><img src=".github/assets/skintoscan-pack-5.svg" width="220" alt="Buy 5 Picture Pack, €19.99 (popular)"></a> <a href="https://skintoscan.com/checkout/?add-to-cart=140"><img src=".github/assets/skintoscan-pack-15.svg" width="220" alt="Buy 15 Picture Pack, €54.99"></a></p>

![usb-rea demo: capture labelled clicks, get the protocol and a working driver](docs/demo.gif)

Got a USB device that only ships a Windows vendor app (case LCD, RGB controller, mouse, "smart" lamp)? Click around in the vendor app while **usb-rea** captures the USB traffic (usbmon on Linux, USBPcap on Windows), diffs the packets per action, infers the protocol, and writes an open-source Python/libusb driver, with every conclusion linked to the exact packets that prove it.

> Status: alpha (v0.7.0, [on PyPI](https://pypi.org/project/usb-rea/)). Validated on synthetic devices, on protocols documented by liquidctl and rivalcfg, and on public Wireshark captures (see [docs/VALIDATION.md](docs/VALIDATION.md)). Not yet tested on a physical gadget: your captures are welcome.

## Try it in 10 seconds (no hardware needed)
```bash
pip install usb-rea
usb-rea demo --device fan
```
```
fan    100%  0x5a | counter (+1 per message) | 0x10 | u16be round(value * 1 + 0) | 0x00 | u16le crc16_modbus(bytes[0:6])
color  100%  0x5a | counter (+1 per message) | 0x20 | round(value * 1 + 0) | round(value[1] * 1 + 0) | round(value[2] * 1 + 0) | u16le crc16_modbus(bytes[0:6])
mode   100%  0x5a | counter (+1 per message) | 0x30 | lookup 1→0x11, 2→0x22, 3→0x47 | 0x00 | 0x00 | u16le crc16_modbus(bytes[0:6])

handshake (3 messages sent once when the app opens the device):
  1. 5a 00 01 00 00 00 0d 1d -> a5 01 ?? ?? ?? ?? ??
  2. 5a 00 02 38 b4 e6 52 1e 1e -> a5 02 01 ??, bytes 3-6 = token from step 1
  3. 5a 00 03 01 00 00 5d 65 -> a5 03 01 ??

device replies:
fan    6/6  0xa5 | = query byte 2 (0x10) | = query byte 1 | u16le round(value * 1 + 0) | sum8(bytes[0:5])
poll 1 7/7  0xa5 | = query byte 2 (0x40) | u16le rpm = raw, seen 794..4012 | u8 temp = raw, seen 35..38 | mode: 0x00 = auto, 0x11 = silent, 0x22 = balanced, 0x47 = turbo | sum8(bytes[0:6])

21 of 21 'seen' observations matched a reply byte (mode, rpm, temp)
```
It writes a synthetic capture of a fan controller (its vendor app first opens a session with a token the fan hands out, then polls the fan's status, and the markers note what the app's screen showed, `seen rpm 1207 temp 37 mode auto`), recovers the protocol and the replies, names the readings and the fan's mode, and writes `report.md` (every claim linked to Wireshark frame numbers) and a working pyusb driver that encodes values it never saw and decodes what the fan answers.

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
| device replies: echoed query bytes, values fitted to labels, readings | status poll → `a5 40 2a 07 26 00 3c` = RPM `u16le` reading, temperature `u8` reading, sum8 |
| named readings, from what the vendor app shows (`seen rpm 1180`) | bytes 2-3 `u16le rpm = raw`, byte 4 `temp = (raw - 40) / 2` |
| on/off status flags (`seen pump on`, `seen pump off`) | byte 5 `bit 0: pump (1 = on)` |
| modes / enum values (`seen mode silent`, `seen mode turbo`) | byte 5 `mode: 0x00 = silent, 0x02 = turbo`, or `bits[4:6] profile: …` beside flags |
| signed readings, when the app shows negative values (`seen temp -5`) | byte 4 `i8 temp = raw`, bytes 2-3 `i16be …` |
| handshake: messages sent once when the app opens the device, session tokens | step 2 bytes 3-6 = bytes 2-5 of the reply to step 1 |

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
Captured on Windows with USBPcap/Wireshark and no markers? Click each action with a short pause in between, then just list them in order, and usb-rea splits the traffic at the pauses:
```bash
usb-rea report lamp.pcapng --labels "brightness 0%; brightness 50%; brightness 100%; power off; power on"
usb-rea scaffold lamp.pcapng --labels labels.txt -o lamp_driver.py   # one label per line
```
(Markers, if you have them, are a JSON list of `{"label", "start", "end"}` epoch timestamps.)

Most vendor apps also poll the device on their own (a "get status" every few hundred ms, keep-alives).
usb-rea spots identical host→device messages sent on a steady rhythm, away from your clicks, and sets
them aside before splitting and diffing; the report lists them under *Background traffic (ignored)*
with their period and frame numbers. A constant "apply" packet that always follows a real command is
not treated as background. Polls that carry a sequence number are caught too: same-shape messages
that differ only in a byte counting up by one (plus a trailing checksum that changes with it) show up
as e.g. `aa 10 ?? 00 ??`. Those need at least 8 copies, so a user stepping a value by one is not
mistaken for a poll.

### Device responses
Devices answer too: an ACK after each command, a status reply to every poll (RPM, temperature,
firmware version), or the data of a GET_REPORT. usb-rea pairs each query with the IN transfer that
follows it (by endpoint and typical delay, so a poll sent in the middle of a click doesn't steal the
click's reply) and decodes the replies with the same machinery: constants, bytes that echo the query
(command id, sequence number), counters, checksums, and values fitted to your labels (`fan 1200` →
`u16le` in the reply). Anything else that varies is reported as a *reading* with its observed range,
and the report says that its meaning is unknown. A 16-bit reading is only claimed when one byte
order changes smoothly and the other jumps. The generated driver gets `query_<name>()` methods that
send the query, read the reply and return a dict (`{"reading_2": 1834, "checksum_ok": True, …}`).
Try it with `usb-rea demo --device fan` or on a capture with polls.

### Naming readings: tell it what the vendor app shows
A reading is just bytes until you say what it is. While capturing, note what the vendor app
displays now and then:
```bash
usb-rea mark -m fan.pcapng.actions.json "seen rpm 1180 temp 34"   # several name/value pairs are fine
```
A `seen` marker is an observation, not an action: it does not end the action in progress, is never
diffed, and never becomes a command. Each observation is compared with the reply just before it
(what the app was showing) or just after it, within 1 s. A reading takes the name when it equals
every observation of that name (2+ observations, within one unit or 1%), or when a linear
`raw = value * scale + bias` fits them exactly and survives the same leave-one-out check as commands
(3+ observations with distinct values). Two neighbouring byte readings are also tried as one 16-bit
LE/BE number, and four as one 32-bit LE/BE number (three are enough when the high byte is still
0x00), so energy counters and uptimes work: `mark "seen energy 2.968"` names bytes 1-4
`u32be energy = raw / 1000`. The report shows the formula with the frames and marker times behind it, and lists
observations that matched nothing; the driver returns `{"rpm": 1180, "temp": 34, "ok": True, …}`.

On/off states work too: `mark "seen pump on, alarm off"` (also `true`/`false`, `yes`/`no`). A name
seen both on and off becomes a status flag, the one bit of a reply byte that is 1 every time the app
said on and 0 every time it said off; several flags can share a byte, and the driver returns
`{"pump": True, "alarm": False, …}`. Two bits that always flip together are left unnamed, and bits
of a flag byte that change but were never named are pointed out in the report.

Modes and other enum values are words: `mark "seen mode silent"`, `mark "seen profile gaming"` (a
word value goes last, or before a comma: `seen mode turbo, rpm 3900`). A name seen as 2+ different
words in 3+ observations becomes a mode: the reply byte whose raw value is the same every time the app
showed one word and different between words. If other bits of that byte change on their own (or it
holds named flags), only the bits that differ between the words are taken, e.g. `bits[4:6] profile`.
The report lists the map (`mode: 0x00 = silent, 0x02 = turbo`) with its evidence, JSON/MCP fields get
it as `table`, and the driver returns the word, or the raw number for a value never seen:
`{"mode": "turbo", …}`. When the app shows a negative number (`seen temp -5`), 8- and 16-bit readings
whose top bit gets set are also tried as signed (`i8`, `i16le`/`i16be`).
A small number that no whole byte matches (`seen battery 3` for battery bars) is also looked for in
part of a byte: the free bits beside named flags or modes (trimmed to the bits that change, so fixed
reserved bits are skipped) or either nibble, e.g. `bits[1:4] battery`; the driver returns the number.
A value shown with decimals (`seen temp 41.5`) is also tried as tenths, hundredths or
thousandths (raw 415, scale 10), so two such markers are enough instead of the three a free linear
fit needs. Numbers can be typed the way the app prints them, with a decimal comma or a thousands
separator: `seen temp 41,5 °C, rpm 1,180` reads as 41.5 and 1180.

Limits: only replies (not commands) are named, a name that fits two places is left out, modes are
one byte (or one contiguous bit group in it) and only the words you saw get a label, 32-bit readings
are never signed, multi-bit numeric readings packed beside other bits are not tried, and display
rounding coarser than one unit (e.g. RPM shown in steps of 10) only works for the identity, not for a
scaled fit. `seen` labels in `--labels` mode have no timestamp and are skipped.

### Handshakes: what the app sends when it opens the device
Many devices want a few messages before they accept commands: a hello, an unlock or auth step, a
"start" or "PC control on". usb-rea treats host→device messages (and class/vendor control reads)
captured before your first action marker as a handshake when they are not background polls and are
never sent again later in the capture, so start capturing before you open the vendor app. Each step
is paired with the reply that follows it, and the report gets a *Handshake* section with the frames.
A run of 3+ reply bytes that comes back in a later handshake request, or at the same offset in every
captured copy of a command, is a session token or device id; a run of 3+ request bytes that the reply
repeats is an echo. A checksum is claimed when one algorithm fits the end of every handshake request
(or every reply). The generated driver replays the handshake in `Device.open()` (called by
`Device()`; `Device(handshake=False)` skips it) before any command: tokens are copied from this
session's live replies into later steps and into commands, request checksums are recomputed, and
each reply is checked against the captured one (`??` for token and checksum bytes, checksums
verified), raising `RuntimeError` on a mismatch. JSON/MCP output has it as `handshake`.

Limits: every handshake message is seen once, so a byte that changes per session but is never reused
(a random nonce the device only reports) looks fixed; `open(check=False)` replays without checking.
Only fixed, linear sequences are replayed: no retries, no branching on the reply, no handshake that
is repeated later (e.g. after a mode switch), and a token must be copied verbatim (a token that is
transformed, such as a challenge answered with a hash, is not recognised). With `--labels` (no
timestamps) the handshake is part of the first action, so use markers for this.

## MCP server
`pip install usb-rea` then add `usb-rea mcp` as a stdio server. Tools: `capture_start`, `capture_stop`, `mark_action`, `diff_actions`, `report`, `scaffold_driver`, `hid_descriptor` (decode a HID report descriptor / report payloads), `wireshark_dissector`, `replay_packet` (refuses unless the human confirmed). Analysis tools accept the same `labels` argument as the CLI for marker-free captures.

With [uv](https://docs.astral.sh/uv/) no install step is needed:
```json
{"mcpServers": {"usb-rea": {"command": "uvx", "args": ["--from", "usb-rea", "usb-rea", "mcp"]}}}
```
For Claude Code: `claude mcp add usb-rea -- uvx --from usb-rea usb-rea mcp`. The server is also listed on the [official MCP Registry](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.emirmrkaljevic/usb-rea) as `io.github.emirmrkaljevic/usb-rea` and on [Glama](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea), which builds it from the repo's `Dockerfile` and checks that it starts and lists its tools.

## How it works
1. `usb-rea capture start`: record traffic (usbmon / USBPcap)
2. `usb-rea mark "brightness 50%"`: label each action you take in the vendor app (`mark "seen rpm 1180"` notes what it displays)
3. `usb-rea diff`: which bytes change per action, value correlation, checksums, counters
4. `usb-rea infer`: message templates + evidence report
5. `usb-rea scaffold`: generate a pyusb driver and replay tests
6. `usb-rea dissector`: write a Wireshark Lua dissector for the inferred protocol
7. `usb-rea replay`: send packets to the device (only with explicit confirmation)
8. `usb-rea hid`: decode a HID report descriptor from a capture (GET_DESCRIPTOR 0x22) or from hex, and decode report payloads
9. `usb-rea mcp`: the same tools as an MCP server for AI agents

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
- [x] device responses: replies to commands, background polls and GET_REPORT decoded, `query_*()` driver methods
- [x] named readings: `seen rpm 1180` markers name and scale reply readings (identity or linear, 8/16/32-bit)
- [x] on/off status flags: `seen pump on` / `seen pump off` name single bits of reply bytes
- [x] modes / enum values (`seen mode turbo`) and signed readings (`seen temp -5`)
- [x] small levels packed beside flags (`seen battery 3` in bits 1-3 of a status byte)
- [x] handshakes: messages sent once when the app opens the device, replayed by the driver with session tokens copied from live replies
- [ ] state machines beyond a fixed handshake (retries, branching on replies, commands only valid in some states)

## Legal
Reverse engineering for interoperability is permitted (EU Directive 2009/24/EC Art. 6, US DMCA §1201(f)). usb-rea only analyzes traffic of devices you own and never redistributes vendor code.

## License
MIT
