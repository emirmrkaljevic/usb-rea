# Changelog

## Unreleased

## v0.5.0 — 2026-10-20
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

## v0.4.0 — 2026-10-19
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

## v0.3.0 — 2026-10-18
Vendor apps that poll the device no longer confuse the analysis.

- background traffic: identical host→device messages sent on a steady rhythm independent of the
  user's clicks (status polls, keep-alives) are detected and set aside before `--labels` splitting
  and diffing; the report gets a *Background traffic (ignored)* section, JSON/MCP output a
  `background` list. Previously a polling vendor app made `--labels` split at the wrong places.
- background polls with a sequence number (a byte counting up by one, optionally with a trailing
  checksum byte) are detected as well; the report shows them with `??` at the changing bytes
- install docs use PyPI (`pip install usb-rea`, `uvx --from usb-rea usb-rea mcp`) instead of git URLs
- releases also publish `server.json` to the official MCP Registry (GitHub OIDC, no token)

## v0.2.1 — 2026-10-16
- multi-packet transactions: actions that send several packets (e.g. write + apply) are inferred as one command; the driver sends all packets in order
- cross-packet checksums (a later packet carrying a checksum of an earlier one)
- fix: `mcp` is now a core dependency, so a plain `pip install usb-rea` gives a working `usb-rea mcp`

- MCP tools: richer descriptions (side effects, privileges, when-to-use) and `pydantic.Field` parameter
  descriptions so Glama TDQS can score the schema; analysis tools accept the same `labels` string/file
  as the CLI for marker-free captures

## v0.2.0 — 2026-10-15
Wireshark dissector generator, HID descriptor decoding, wider inference, marker-free captures.

- `usb-rea dissector` (MCP tool `wireshark_dissector`): generate a Wireshark Lua dissector for the inferred protocol —
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

## v0.1.0 — 2026-10-14
First public release.

- pcap/pcapng parser for Linux usbmon (DLT 189/220) and Windows USBPcap (DLT 249), pure Python
- action markers (`usb-rea mark`) and per-action diffing with background-traffic filtering
- inference: constants, command ids, linear 8/16-bit LE/BE values, multi-value actions, lookup tables,
  rolling counters, sum/xor/CRC8/CRC16 checksums; leave-one-out guard against coincidental fits
- Markdown evidence report: every claim linked to Wireshark frame numbers
- standalone pyusb driver generator (bulk/interrupt and control/HID SET_REPORT)
- confirmed-only replay, CLI, MCP server (capture, mark, diff, report, scaffold, replay)
- validation: synthetic devices, liquidctl Kraken X, rivalcfg Rival 100, public Wireshark captures
