# Changelog

## Unreleased

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
