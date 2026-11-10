# Changelog

## Unreleased
Larger offline `usb-rea lookup` table, a known-devices page, and clearer lookup errors.
- `usb-rea lookup`: the offline known-device table now covers the USB IDs documented by
  liquidctl (Kraken, Hydro, Asetek, Commander, HUE 2, Aura, Lian Li Uni, Aquacomputer and
  others), every rivalcfg SteelSeries mouse, further turing-smart-screen-python revisions
  (rev C/D, WeAct, native USB Turing screens), linux-thermalright-lcd-control, and a
  curated OpenRGB set (Thermaltake Riing, Cooler Master ARGB hubs, plus IDs those projects
  share). Each entry cites the public source file. Listed in `docs/known-devices.md`.
- `usb-rea lookup` also accepts the `ID 1e71:170e` form from `lsusb`. A bad argument now
  says a VID:PID or a capture path was expected, instead of only showing the parse error.

## v0.7.12 (2026-11-10)
Look up a VID:PID against known open-source drivers before capturing, plus a short README TL;DR and vs Wireshark section.
- `usb-rea lookup VID:PID` (or a capture file) and the MCP tool `lookup_device`: before capturing,
  says whether an open-source project already documents the device's protocol (liquidctl Kraken X/Z
  and Hydro Platinum family, rivalcfg Rival 100/105, turing-smart-screen-python, linux-thermalright-lcd-control,
  usb-rea case studies) with links, notes and limits, plus vendor/product names from the local
  `usb.ids`. Offline by default; `--online` also queries OpenDeviceDB's read-only API (only the ID
  is sent) and reports the error instead of failing when there is no network. Unknown IDs stay
  unknown. Suggested in Discussion #3.
- docs: short TL;DR and a "How is this different from Wireshark?" section near the top of the README.

## v0.7.11 (2026-11-06)
BMP and WebP image streams, plus ASUS TUF LC III LCD case study docs.
- image streams: WebP frames (`RIFF....WEBP` magic, RIFF chunk size for frame length, width/height from
  VP8X canvas or VP8L/VP8 bitstream) are found the same way as JPEG/PNG/GIF/BMP;
  `send_image()` accepts WebP file bytes. Synth: `make_capture(..., image_stream=True, webp=True)`;
  `usb-rea demo --device lcd --webp`.
- image streams: Windows BMP frames (`BM` magic, `bfSize` frame length, width/height from
  BITMAPINFOHEADER including top-down negative height) are found the same way as JPEG/PNG/GIF;
  `send_image()` accepts BMP file bytes. Synth: `make_capture(..., image_stream=True, bmp=True)`;
  `usb-rea demo --device lcd --bmp`.
- docs: ASUS TUF Gaming LC III LCD case study from the trimmed real USBPcap fixture
  (`docs/case-study-asus-tuf-lc3.md`), linked from VALIDATION and README.

## v0.7.10 (2026-11-04)
Raw screen streams whose draw command starts the first pixel packet.
- raw image streams whose draw command is the start of the frame's first pixel packet (no packet of
  its own): the region fields are read from the start of each frame, and the reading is kept where
  every frame is that many pixels plus a command of the same length (up to 32 bytes). `streams`
  gains `header_inline`; the report says "Command at the start of each frame's first packet", the
  byte order and test card are read after the command, a byte count field counts only the pixels,
  and `send_image()` puts the command in front of the pixels before cutting them into packets.
- synth: `make_capture(..., raw="rgb565", inline=True)`; `usb-rea demo --device lcd --raw rgb565 --inline`.

## v0.7.9 (2026-11-03)
States the device reports, and mode switches inside an action.
- states the device reports: a command the app only sent while a named status reply byte (a
  `seen mode turbo` mode or an on/off flag) showed one value gets `requires` with `source: "reply"`
  (reply, byte, value, count, other values, reply and command frames, and the `setter` command that
  made the reply show that value, if any). The report and CLI demo list it; the driver reads the
  status first and switches with the setter, or raises `StateError`.
- mode switches inside an action: a multi-packet action whose first packet is a state command with
  one fixed value, and whose last packet (if any) puts back the value from before or one fixed value,
  keeps only its own packets and gets `switch` (also under `switches`). The driver sends the state
  command around the action, as the app did.
- synth: `make_capture(..., device="fan", reported=True)` (`press mode N` labels for the fan's own
  button) and `make_capture(..., device="fan", switch=True)`.

## v0.7.8 (2026-11-02)
Image streams whose frames span several endpoints.
- image streams over several endpoints: for a device with more than one host->device channel the
  channels are also merged by time, so frames whose packets alternate between two endpoints, go to
  one endpoint and then another, or whose draw command goes to the command endpoint are found as one
  stream (kept only when most frames really span endpoints and it explains as many frames and packets
  as the per-endpoint guesses; two screens with their own frame rates stay two streams). `streams`
  gains `endpoints`, `endpoint_layout` (`alternate`, `blocks`) and `header_endpoint`; the report
  lists them and `send_image()` writes each packet and the draw command to the right endpoint.
- synth: `make_capture(..., image_stream=True, endpoints="alternate"|"blocks"|"command")`;
  `usb-rea demo --device lcd --endpoints alternate`.

## v0.7.7 (2026-11-01)
RGB or BGR on raw screen streams, settled with a test card.
- raw image streams: RGB or BGR channel order. Pixels alone can't tell red from blue, so it is
  settled by frames that show the new test card (`usb-rea testcard`, a PNG that is 1/2 red, 1/4
  green, 1/8 blue, 1/8 white; the shares survive scaling, rotation and mirroring). Only one reading
  of the pixels (RGB or BGR, and for RGB565 little or big endian) gets them right. `streams` gains
  `channel_order` (`rgb`, `bgr` or null for unknown) and `channel_evidence` (frames checked and
  matched, agreement, confidence); below 90% agreement it stays unknown. A test card also settles
  the RGB565 byte order. The report has a "Channel order" line, and `send_image()` swaps red and
  blue for a BGR screen (RGB when unknown).
- synth: `make_capture(..., raw=..., testcard="rgb"|"bgr")` shows the test card in a few frames;
  `usb-rea demo --device lcd --raw rgb565 --testcard bgr`.

## v0.7.6 (2026-10-31)
A real user's LCD capture as a test, and two fixes it found.
- USBPcap: control IN data that arrives in the "complete" record (stage 3) is read, so VID:PID is
  found in captures where the GET_DESCRIPTOR reply was missed before.
- tests: a trimmed, blanked copy of a real ASUS TUF Gaming LC III LCD capture (shared in
  liquidctl#936) checks the brightness command and the JPEG stream end to end.
- image streams: the per-frame ack is counted per frame (a fixed device->host message between one
  frame's start and the next) instead of over the whole capture, so bursts of acks while no frames
  go out no longer hide it, and the acks are no longer mistaken for replies to a command. `ack`
  gains `frames_acked`.

## v0.7.5 (2026-10-30)
Raw pixel streams to a screen.
- raw image streams: RGB565 and RGB888 pixels with no image file format are found by size. Runs of
  large host->device packets with no pause between them whose payload is a common screen size
  (width x height x 2 or 3), or the region a short draw command sent just before names (x, y, width,
  height or x0, y0, x1, y1 as 16-bit LE/BE fields, or four packed 10-bit fields as on the Turing
  Smart Screen rev A), are frames of a stream when there are at least 3. Partial redraws count with
  a region; one transfer per frame and frames sent back to back are split by the screen size. The
  pixels and draw commands are set aside like JPEG streams, other commands on the endpoint stay.
  `streams` gains `raw`, `header_packet`, `region`, `length_field`, `byteorder` (RGB565 order from
  pixel smoothness), `size_alternatives`, `frame_bytes` and `regions`; the report has a raw variant
  of the "Image stream" section.
- 16-bit header fields: a packet count or index above 255 in a per-packet header is read as a u16
  (`nn nn`, `ii ii`, with `count_width`/`count_endian`, `index_width`/`index_endian`); the driver
  fills it in.
- driver `send_image()` takes a Pillow image (converted to RGB565 in the captured byte order, or
  RGB888) or raw pixel bytes for a raw stream, writes the draw command with the region filled in and
  can redraw part of the screen (`x`, `y`, `size`).
- synthetic raw LCD: `make_capture(..., device="lcd", image_stream=True, raw="rgb565" | "rgb888")`,
  `usb-rea demo --device lcd --raw rgb565`; tests include a Turing Smart Screen rev A fixture written
  from its public protocol description.

## v0.7.4 (2026-10-29)
Image streams to a screen.
- image streams: host->device channels whose packets start a JPEG, PNG or GIF at the same offset in
  at least 3 frames are an image stream (a picture or video for an LCD). Its packets (frames run to
  the image end marker, chunks cut off by the start of the capture are matched by their header) and
  the device's per-frame ack are set aside before anything else, so a brightness write on another
  endpoint is no longer merged with the video. `streams` lists endpoint, format, frames, packets per
  frame, image size (JPEG SOF, PNG IHDR), frame rate, chunk size and padding, header pattern (`nn`
  packet count, `ii` index) and the ack; the report has an "Image stream" section, the CLI demo and
  MCP output list it, and the generated driver gets `send_image(jpeg_bytes)`. Synthetic LCD:
  `make_capture(..., device="lcd", image_stream=True)`, used by `usb-rea demo --device lcd`.

## v0.7.3 (2026-10-28)
Commands that only work in one mode.
- state preconditions: a command the app only sent while a state command (one argument that is a
  lookup table, like `mode 1/2/3`, or on/off) had one value, at least twice and while other commands
  were used in other values, gets `requires` (state, value, count, other values, evidence frames).
  The report, the CLI demo and the MCP output (`states`) list it; the generated driver tracks what it
  set and calls the state command first (`Device(auto_state=False)` raises `StateError` instead).
  Synthetic fan: `make_capture(..., device="fan", states=True)` (color only in mode 3), used by
  `usb-rea demo --device fan`.

## v0.7.2 (2026-10-27)
Handshakes that branch on the device's reply.
- handshake branches: when a later handshake block follows the first one up to a step whose reply
  differs at a byte that is not a token or checksum (a status or mode the device reports) and then
  sends other messages, that step gets `branches` (reply byte offset, each value seen with its count
  and the steps the app sent next, the most common value as `default`). The branch messages are kept
  out of the actions, the report and the CLI demo list the branches, and the driver's `open()` reads
  the byte from the live reply and replays the matching branch, falling back to the most common one
  for a value never captured (`Device.branches` records what was taken). Synthetic fan:
  `make_capture(..., handshake=True, branch=True)` (auth answers "needs calibration" once, and the app
  sends a calibrate step before start); `usb-rea demo --device fan` shows it.

## v0.7.1 (2026-10-26)
Handshake retries and reopens.
- handshake retries: identical messages the app sends again straight away (after no reply or a
  different, busy reply) are one handshake step with the earlier copies under `retries`; the report
  lists them and the driver's `open()` resends such a step up to as many times as the app did when
  the reply times out or does not match.
- handshake reopens: when the app sends the whole handshake again later (device woke up, app
  reconnected), each message matching its step except for the checksum or a new session token,
  that block is kept out of the actions and listed under `reopens`; the report notes it. Synthetic
  fan: `make_capture(..., handshake=True, reopen=True)`.

## v0.7.0 (2026-10-24)
Session handshakes and small levels packed into part of a byte.
- handshakes: host→device messages (and class/vendor control reads) sent before the first action
  marker, that are not background polls and are never sent again, are reported as the session setup
  the vendor app does when it opens the device, each with its reply. A run of 3+ reply bytes reused
  in a later handshake request or in every copy of a command is noted as a session token, a request
  run repeated in the reply as an echo, and a checksum shared by all handshake requests (or replies)
  is recognised. Report: *Handshake* section with frames; JSON/MCP: `handshake`; the driver replays
  it in `Device.open()` before any command, copying tokens from live replies, recomputing request
  checksums and checking the fixed reply bytes. Only fixed linear sequences for now (no retries or
  branching), so the state machine roadmap item stays open
- synthetic fan: `make_capture(..., handshake=True)` opens a session (hello, auth with the token
  from the hello reply, start); `usb-rea demo --device fan` shows it
- small levels in part of a byte: when no whole reading matches a `seen` number (`seen battery 3`),
  the free bits beside named flags or modes, or either nibble of a byte, are tried; fixed reserved
  bits are trimmed off, a level that fits two places is left out with a note, and the driver returns
  the number (`{"charging": True, "battery": 4}`)

## v0.6.1 (2026-10-23)
Decimal readings and numbers in other locales.

- decimal readings: a `seen` value shown with decimals (`seen temp 41.5`) is also matched as
  tenths, hundredths or thousandths of the raw number (raw 415, scale 10), so two markers are
  enough; whole numbers on screen are never read that way
- `seen` markers accept numbers as Windows apps print them in other locales: a decimal comma
  (`seen temp 41,5 °C`) and a thousands separator (`seen rpm 1,180`); a comma followed by a space
  still separates two readings

## v0.6.0 (2026-10-21)
32-bit readings, named device modes and signed values.

- named readings can be 32-bit: four neighbouring reply readings (or three plus a 0x00 high byte,
  for counters below 2**24) are tried as one u32 LE/BE number, so `seen energy 2.968` or
  `seen uptime 86400` can name an energy counter or uptime; report and driver show `u32le`/`u32be`
- named modes / enum values: a `seen` value that is a word (`seen mode silent`, `seen profile gaming`;
  last in the marker or before a comma) is kept as text. A name seen as 2+ different words in 3+
  observations is matched to the reply byte that has one raw value per word and different values for
  different words; when other bits of the byte change on their own, or it holds named flags, only the
  contiguous bits that differ between the words are taken (`bits[4:6] profile: …`). Both bytes of an
  unnamed u16 reading are tried as well. Ambiguous modes and names seen both as numbers and as words
  are left unnamed with a note. Report: `mode: 0x00 = silent, 0x02 = turbo` with an evidence table
  that shows every word; JSON/MCP fields gain `table` (raw → word); `query_<name>()` returns the word,
  or the raw number for a value never seen
- signed readings: when the app showed a negative value (`seen temp -5`), 8/16-bit readings whose top
  bit gets set are also tried as two's complement (`i8`, `i16le`/`i16be`; field `signed`)
- synthetic fan with `observe=True`: the status reply's spare byte reports the current mode
  (`auto`/`silent`/`balanced`/`turbo`) and the markers note it, so `usb-rea demo --device fan` names it

## v0.5.0 (2026-10-20)
Readings and status flags get the names the vendor app shows for them.

- named readings: `usb-rea mark "seen rpm 1180 temp 34"` notes what the vendor app displays. These
  observation markers never become actions or affect diffing/segmentation; they are matched to the
  reply just before (or after) them, and a reply reading that equals them (identity) or fits
  `raw = value * scale + bias` with the leave-one-out guard (3+ observations) gets the name. Two
  neighbouring byte readings are also tried as u16 LE/BE. JSON/MCP fields gain `name` (with
  `scale`/`bias` and the observations in `observed`), and the output a top-level `observations`
  list; the report shows each formula with its frames and marker times plus an *Observations*
  section that lists unmatched values; `query_<name>()` returns e.g. `{"rpm": 1180, "temp": 34, "ok": True}`
- on/off status flags: `seen pump on, alarm off` (also true/false, yes/no) counts as 1/0. A name seen
  both on and off is matched to the single bit of a reply byte reading that is 1 exactly when the app
  said on; several flags can share a byte, two bits that always flip together are left unnamed (note),
  and other changing bits of a flag byte are noted. Report: `bit N: name (1 = on)` and an on/off
  evidence table; observations match e.g. `byte 1 bit 0`; the driver's `query_<name>()` returns booleans
- synthetic fan: `make_capture(..., observe=True)` adds `seen` markers; `usb-rea demo --device fan` uses them

## v0.4.0 (2026-10-19)
The device's answers are decoded too, not only what the vendor app sends.

- device responses: each host query (command, background poll, class/vendor control read such as
  GET_REPORT) is paired with the device→host transfer that answers it, and the replies are decoded:
  constants, echoed query bytes (command id, sequence number), counters, checksums, values fitted to
  the action labels (same leave-one-out guard as commands), and *readings* with their observed range
  for anything that varies on its own. Report section *Device responses* with query/reply frames,
  `responses` in JSON/MCP output, and `query_<name>()` methods in the generated driver that send the
  query and return the decoded reply
- pairing survives a poll sent between a command and its reply (replies go to the query whose delay
  matches its group's typical delay)
- synthetic fan: replies `a5 <cmd> <seq> <arg u16le> <sum8>` and, with `poll=`, a status reply with
  current RPM and temperature, for ground-truth tests

## v0.3.0 (2026-10-18)
Vendor apps that poll the device no longer confuse the analysis.

- background traffic: identical host→device messages sent on a steady rhythm independent of the
  user's clicks (status polls, keep-alives) are detected and set aside before `--labels` splitting
  and diffing; the report gets a *Background traffic (ignored)* section, JSON/MCP output a
  `background` list. Previously a polling vendor app made `--labels` split at the wrong places.
- background polls with a sequence number (a byte counting up by one, optionally with a trailing
  checksum byte) are detected as well; the report shows them with `??` at the changing bytes
- install docs use PyPI (`pip install usb-rea`, `uvx --from usb-rea usb-rea mcp`) instead of git URLs
- releases also publish `server.json` to the official MCP Registry (GitHub OIDC, no token)

## v0.2.1 (2026-10-16)
- multi-packet transactions: actions that send several packets (e.g. write + apply) are inferred as one command; the driver sends all packets in order
- cross-packet checksums (a later packet carrying a checksum of an earlier one)
- fix: `mcp` is now a core dependency, so a plain `pip install usb-rea` gives a working `usb-rea mcp`

- MCP tools: richer descriptions (side effects, privileges, when-to-use) and `pydantic.Field` parameter
  descriptions so Glama TDQS can score the schema; analysis tools accept the same `labels` string/file
  as the CLI for marker-free captures

## v0.2.0 (2026-10-15)
Wireshark dissector generator, HID descriptor decoding, wider inference, marker-free captures.

- `usb-rea dissector` (MCP tool `wireshark_dissector`): generate a Wireshark Lua dissector for the inferred protocol:
  command names in the Info column, decoded values, counters, lookup labels, checksum verification with expert info;
  tested against real tshark 4.4 in CI. `usb-rea demo` now writes `<device>.lua` too
- synthetic captures: submission and completion now share one URB id and use proper usbmon data flags,
  so Wireshark pairs requests with responses (GET DESCRIPTOR responses and VID/PID are decoded)
- `--labels`: analyse plain Wireshark/USBPcap captures without markers by splitting traffic at the pauses between clicks
- inference: 32-bit LE/BE linear values and packed bitfields (contiguous bits beside non-zero const bits,
  including 12-bit spans across two LE bytes); synthetic `dial` device + encode round-trip tests
- HID report descriptor decoder (`usb-rea hid`, MCP tool `hid_descriptor`): items, reports, bit-exact fields,
  report IDs, Push/Pop, extended usages, payload decoding; checked against the HID 1.11 boot mouse/keyboard descriptors
- reports include a HID section and tag each inferred command with its HID report when the capture has GET_DESCRIPTOR 0x22
- Dockerfile and glama.json so the MCP server can be listed on Glama
- `usb-rea demo --device dial` (32-bit value + bitfield demo); README capability table, MCP tool list and roadmap
  updated for 32-bit/bitfield inference and `hid_descriptor`
- registry metadata: `server.json` (official MCP Registry, `mcp-name` marker in README) and `smithery.yaml`
- listed on Glama (score badge in README); MCP install snippets now use the git URL so they work before the PyPI release

## v0.1.0 (2026-10-14)
First public release.

- pcap/pcapng parser for Linux usbmon (DLT 189/220) and Windows USBPcap (DLT 249), pure Python
- action markers (`usb-rea mark`) and per-action diffing with background-traffic filtering
- inference: constants, command ids, linear 8/16-bit LE/BE values, multi-value actions, lookup tables,
  rolling counters, sum/xor/CRC8/CRC16 checksums; leave-one-out guard against coincidental fits
- Markdown evidence report: every claim linked to Wireshark frame numbers
- standalone pyusb driver generator (bulk/interrupt and control/HID SET_REPORT)
- confirmed-only replay, CLI, MCP server (capture, mark, diff, report, scaffold, replay)
- validation: synthetic devices, liquidctl Kraken X, rivalcfg Rival 100, public Wireshark captures
