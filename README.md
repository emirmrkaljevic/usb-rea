# usb-rea: Reverse Engineer any USB gadget

<!-- mcp-name: io.github.emirmrkaljevic/usb-rea -->

[![ci](https://github.com/emirmrkaljevic/usb-rea/actions/workflows/ci.yml/badge.svg)](https://github.com/emirmrkaljevic/usb-rea/actions/workflows/ci.yml) ![license](https://img.shields.io/badge/license-MIT-blue) [![usb-rea MCP server](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea/badges/score.svg)](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea)

<p align="center"><a href="https://skintoscan.com/#packages"><img src=".github/assets/skintoscan-support.svg" width="684" alt="Support my open-source work: get a SkinToScan pack"></a><br><sub>If you find this useful, you can support me by getting a SkinToScan pack, my other project. It's a one-time purchase that directly funds my open-source work.</sub></p>
<p align="center"><a href="https://skintoscan.com/checkout/?add-to-cart=138"><img src=".github/assets/skintoscan-pack-1.svg" width="220" alt="Buy Single Picture Check, €4.49"></a> <a href="https://skintoscan.com/checkout/?add-to-cart=139"><img src=".github/assets/skintoscan-pack-5.svg" width="220" alt="Buy 5 Picture Pack, €19.99 (popular)"></a> <a href="https://skintoscan.com/checkout/?add-to-cart=140"><img src=".github/assets/skintoscan-pack-15.svg" width="220" alt="Buy 15 Picture Pack, €54.99"></a></p>

**Concrete result:** from captures of the NZXT Kraken X (1e71:170e) fan command, usb-rea recovers `02 4d <channel> 00 <duty>` byte for byte, exactly as liquidctl's `kraken2.py` sends it, and the generated driver emits identical packets for duty values it never saw. Same for the SteelSeries Rival 100 (1038:1702) DPI, polling and RGB tables from rivalcfg. Proof runs in CI: [docs/VALIDATION.md](docs/VALIDATION.md). Full walk-through with a CRC8 and a rolling counter: [Corsair Hydro Platinum case study](docs/case-study-hydro-platinum.md).

**Have a Windows-only device?** [Open a device request](https://github.com/emirmrkaljevic/usb-rea/discussions/1) with a capture and I will run it and publish the result.

![usb-rea demo: capture labelled clicks, get the protocol and a working driver](docs/demo.gif)

Got a USB device that only ships a Windows vendor app (case LCD, RGB controller, mouse, "smart" lamp)? Click around in the vendor app while **usb-rea** captures the USB traffic (usbmon on Linux, USBPcap on Windows), diffs the packets per action, infers the protocol, and writes an open-source Python/libusb driver, with every conclusion linked to the exact packets that prove it.

> Status: alpha (v0.7.5, [on PyPI](https://pypi.org/project/usb-rea/)). Validated on synthetic devices, on protocols documented by liquidctl and rivalcfg, on public Wireshark captures (see [docs/VALIDATION.md](docs/VALIDATION.md)) and on a real AIO cooler LCD capture a user shared, where it found the same brightness command and image stream format the user had worked out by hand. Your captures are welcome.

## Try it in 10 seconds (no hardware needed)
```bash
pip install usb-rea
usb-rea demo --device fan
```
```
mode         100%  0x5a | counter (+1 per message) | 0x30 | lookup 1→0x11, 2→0x22, 3→0x47 | 0x00 | 0x00 | u16le crc16_modbus(bytes[0:6])
fan          100%  0x5a | counter (+1 per message) | 0x10 | u16be round(value * 1 + 0) | 0x00 | u16le crc16_modbus(bytes[0:6])
color        100%  0x5a | counter (+1 per message) | 0x20 | round(value * 1 + 0) | round(value[1] * 1 + 0) | round(value[2] * 1 + 0) | u16le crc16_modbus(bytes[0:6])
  color only sent while mode 3 (3x; other commands ran in mode 1, 2): the driver sets it first

handshake (3 messages sent once when the app opens the device):
  1. 5a 00 01 00 00 00 0d 1d -> a5 01 ?? ?? ?? ?? ??, sent again 2x later (session reopened)
  2. 5a 00 02 38 b4 e6 52 1e 1e -> a5 02 ?? ??, bytes 3-6 = token from step 1, sent again 2x later (session reopened)
     reply byte 2 = 01 (2x, most common): the steps below
     reply byte 2 = 02 (1x): 5a 00 04 01 00 00 5c 11 -> a5 04 01 ??, 5a 00 03 01 00 00 5d 65 -> a5 03 01 ??
  3. 5a 00 03 01 00 00 5d 65 -> a5 03 01 ??, sent again 1x later (session reopened)

device replies:
mode         6/6  0xa5 | = query byte 2 (0x30) | = query byte 1 | = query byte 3 | 0x00 | sum8(bytes[0:5])
fan          6/6  0xa5 | = query byte 2 (0x10) | = query byte 1 | u16le round(value * 1 + 0) | sum8(bytes[0:5])
color        6/6  0xa5 | = query byte 2 (0x20) | = query byte 1 | 0x00 | 0x00 | sum8(bytes[0:5])
poll 1       7/7  0xa5 | = query byte 2 (0x40) | u16le rpm = raw, seen 800..4011 | u8 temp = raw, seen 35..38 | mode: 0x11 = silent, 0x22 = balanced, 0x47 = turbo | sum8(bytes[0:6])

24 of 24 'seen' observations matched a reply byte (mode, rpm, temp)
```
It writes a synthetic capture of a fan controller (its vendor app first opens a session with a token the fan hands out, then polls the fan's status, and the markers note what the app's screen showed, `seen rpm 1207 temp 37 mode silent`), recovers the protocol and the replies, names the readings and the fan's mode, notices that the app only sets a color in mode 3, and writes `report.md` (every claim linked to Wireshark frame numbers) and a working pyusb driver that encodes values it never saw and decodes what the fan answers.

`--device lamp` (default) is a simple 8-bit device; `--device lcd` is a pump cap screen whose app streams a JPEG video while you change the brightness; `--device dial` shows 32-bit values and packed bitfields:
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
| image streams to a screen, kept apart from the commands | JPEG on EP 0x03, header `08 nn 00 80` then `08 ii 00 00`, ack `08 81` per frame |
| raw pixel streams (RGB565/RGB888), found by size and by the region the draw command names | 320x480 RGB565 LE after `rr rr rr rr rr c5` (Turing Smart Screen rev A) |

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

Retries are recognised: when the app sends the same message again straight away because the first
copy got no reply or a different one (a device that answers "busy" until it is ready), the copies
are one step with the earlier ones listed under `retries`. The driver then resends that step up to
as many times as the app did when the reply times out or does not match.

Reopens are recognised too: when the app sends the whole handshake again later in the capture (the
device slept or was replugged, or the app reconnected), with each message on the same channel and
length and only the checksum or bytes copied from that block's own replies (a new session token)
changed, the block is session setup, not part of an action. It is kept out of the actions, the
steps list it under `reopens`, and the report says so.

Branches on the device's reply are recognised as well: when a later block follows the handshake up
to some step and then sends other messages, and the reply to that step differs from the first
session's at a byte that is not a session token or checksum (a status such as "ready" or "needs
calibration", or a mode), that step gets `branches`: the reply byte's offset, each value seen there
with how often and the steps the app sent next (the rest of the handshake for the first session's
value, the other messages up to the next action marker for the others), and the most common value
as `default`. The byte becomes `??` in *Expected*, the branch messages are kept out of the actions,
and the report and `usb-rea demo --device fan` list the branches (the synthetic fan's app sends a
calibrate step when auth answers "needs calibration", `make_capture(..., handshake=True, branch=True)`).
The driver's `open()` reads that byte of the live reply and replays the matching branch, falling back
to the most common one for a value the capture never showed; `Device.branches` records the values taken.

Limits: every handshake message is seen once, so a byte that changes per session but is never reused
(a random nonce the device only reports) looks fixed; `open(check=False)` replays without checking.
Branching is learned from one capture only (the first session and its reopens, so capture the app
reconnecting in the states you care about), with one branch point per handshake decided by one reply
byte; branches that join again are stored as separate tails, and a branch block must sit between
actions (not inside a marker). Otherwise a later handshake must repeat the whole sequence to count as
a reopen (a partial one, e.g. after a mode switch, is not recognised), and a token must be copied verbatim (a token that is
transformed, such as a challenge answered with a hash, is not recognised). With `--labels` (no
timestamps) the handshake is part of the first action, so use markers for this.

### States: commands the app only sends in one mode

Some devices only accept a command in one mode (a color only in "custom" lighting mode, a curve only
in manual fan mode), so the vendor app switches the mode first. usb-rea walks the actions in capture
order and tracks the value last chosen by each state command (a command with one argument that is a
lookup table, like `mode 1/2/3`, or an on/off label). A command gets `requires` (state, value, how
often, the other values seen, evidence frames) when it was sent at least twice, every time after the
state command chose the same value, while the capture also shows other commands used in a different
value of that state. The report adds an "Only sent while `mode 3`" line, the CLI demo and the MCP
`diff_actions` output list it under `states`, and the generated driver remembers what it set:
`set_color()` first calls `set_mode(3)` unless the driver already set mode 3 since `open()`, and
`Device(auto_state=False)` raises `StateError` instead. The synthetic fan's app only sets a color in
mode 3 (`make_capture(..., device="fan", states=True)`, used by `usb-rea demo --device fan`).

Limits: this is what the app did, not proof that the device refuses the command in other modes;
capture the command in every mode you can to avoid a false precondition. Commands sent before any
state command count as unknown and give no precondition, the state the device starts in is not read
back (the driver sets the mode on the first gated call after `open()`), a reopened session resets
what the driver knows, and states reported only in device replies, or a mode the app switches inside
the same action, are not tracked yet.

### Image streams: pictures and video sent to a screen

Devices with a screen (AIO pump caps, keyboards and stream decks with an LCD) often get a picture or
a whole video from the vendor app the entire time you click around: tens of thousands of large
packets on one endpoint. Diffed as actions, that traffic buries the few real commands, so a
brightness change gets read as "byte 1 of the video". usb-rea first looks for host→device channels
where packets start an image (JPEG `FF D8 FF`, PNG, GIF) at the same offset in at least 3 frames.
That offset is the per-packet header; a frame runs until the image's end marker (JPEG `FF D9`, with
embedded thumbnails counted, PNG `IEND`), the next start or a pause. Each header byte is described
as constant, `nn` (packets in the frame) or `ii` (the packet's index), chunks cut off at the start
of the capture are recognised by that header, and a fixed device→host message sent about once per
frame is the ack. All of it is set aside before background polls, handshakes and actions are
analysed, so the commands come from the remaining traffic.

The report gets an "Image stream" section (endpoint, format, frames, packets per frame, image size
read from the JPEG SOF / PNG IHDR, frame rate, chunk size and padding, header pattern, ack), the MCP
`diff_actions` output has `streams`, and the generated driver gets `send_image(jpeg_bytes)`, which
cuts an image into chunks behind the captured header, fills in the count and index bytes, pads the
last chunk and returns the ack. The synthetic LCD streams a 240x240 JPEG video at 20 frames per
second next to its brightness command (`make_capture(..., device="lcd", image_stream=True)`, used by
`usb-rea demo --device lcd`). On a real AIO pump LCD capture (75,788 image packets, 8,670 frames of
a 320x320 JPEG, four brightness writes on another endpoint) this turns a wrong "brightness" made of
video bytes into the right one: byte 4 = percent on EP 0x01.

Raw pixel streams have no magic bytes, so they are found by size. Many cheap case and AIO screens
take plain RGB565 (2 bytes a pixel) or RGB888 (3 bytes) behind a short draw command. On one
host→device channel usb-rea looks for runs of large packets with no pause between them (all but the
last the same length) whose payload is exactly width x height x bytes per pixel for a common screen
size (80x160 up to 1920x480, both orientations), or exactly the region the short packet sent just
before the run names: x, y, width, height or x0, y0, x1, y1 as 16-bit fields (little or big endian),
or four 10-bit fields packed into 5 bytes as on the Turing Smart Screen rev A. With a region, partial
redraws (a clock, a sensor value) count as frames of the same stream. Per-packet headers are found
the same way as for JPEG, and a packet count or index above 255 is now read as a 16-bit field
(`nn nn`, `ii ii`, with its byte order). A 16- or 32-bit byte count in the draw command is marked
`ll`. For RGB565 the pixel byte order is the one that makes neighbouring pixels smoother. One
transfer per frame (a whole screen handed to the USB stack at once) and several frames back to back
in one run are split by the screen size. The draw command packets are set aside with the pixels;
other commands on the same endpoint (hello, brightness, orientation) stay commands.

The report then says "Raw RGB565 pixels", the screen size and frame size, other sizes with the same
byte count, the byte order, the region fields and how many frames redraw only part of the screen,
and the draw command pattern (`xx`/`yy` position, `ww`/`hh` size, `ex`/`ey` end position, `rr`
packed region, `ll` byte count). The driver's `send_image()` takes a Pillow image (converted to
RGB565 in the captured byte order, or RGB888; Pillow is not needed otherwise) or bytes already in
that format, writes the draw command with the region filled in and then the pixels, so
`send_image(clock, x=100, y=8, size=(48, 16))` redraws just a corner. The synthetic LCD can stream
raw pixels too: `make_capture(..., device="lcd", image_stream=True, raw="rgb565")` (160x128, draw
command with x, y, width, height as u16 LE, every 4th frame a 48x16 clock) or `raw="rgb888"` (128x160,
64-byte packets with a u16 LE packet index and count), used by `usb-rea demo --device lcd --raw rgb565`.
The tests also check a Turing Smart Screen rev A fixture written from its public protocol
description (6-byte commands, `DISPLAY_BITMAP` = 197, RGB565 little-endian pixels).

Limits: images split over several endpoints are not detected yet. A raw stream needs at least 3
frames whose payload is a listed screen size or matches the region fields; a screen size not in the
list without a region command is missed, and the same byte count can fit several sizes (320x480
RGB565 is also 480x320, and 320x320 RGB888), which the report lists so you can check on the device.
Region fields are only looked for in the separate draw command (not inside the first pixel packet),
width and height are expected in that order, RGB888 channel order (RGB or BGR) is not worked out,
and a frame with a pause longer than 30 ms inside it is split. `send_image()` does not resize or
re-encode (send an image of the captured size and format), and a stream needs at least 3 frames in
the capture.

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
- [x] handshake retries: a step the app resent after no reply or a busy reply is resent by the driver too
- [x] handshake reopens: the whole handshake sent again mid-capture is kept out of the actions
- [x] handshake branches: the next steps chosen by a byte of the device's reply, replayed by the driver from the live reply
- [x] state preconditions: commands the app only sent after a mode command chose one value, set first by the driver
- [ ] states read from device replies and mode switches inside an action
- [x] image streams: JPEG/PNG/GIF frames sent to a screen are kept apart from the commands, `send_image()` in the driver
- [x] raw pixel streams (RGB565/RGB888 without an image header) and 16-bit header fields
- [ ] image streams split over several endpoints, RGB888 channel order

## Legal
Reverse engineering for interoperability is permitted (EU Directive 2009/24/EC Art. 6, US DMCA §1201(f)). usb-rea only analyzes traffic of devices you own and never redistributes vendor code.

## License
MIT
