# Changelog

## Unreleased
- HID report descriptor decoder (`usb-rea hid`, MCP tool `hid_descriptor`): items, reports, bit-exact fields,
  report IDs, Push/Pop, extended usages, payload decoding; checked against the HID 1.11 boot mouse/keyboard descriptors
- reports include a HID section and tag each inferred command with its HID report when the capture has GET_DESCRIPTOR 0x22
- Dockerfile and glama.json so the MCP server can be listed on Glama

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
