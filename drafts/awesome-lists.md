<!-- DRAFT PR texts — opening PRs on other repos needs Emir's OK. Checked 14 Oct 2026. -->

| # | Target repo | Stars | Section | Status / note |
|---|---|---|---|---|
| 1 | punkpeye/awesome-mcp-servers | 96k | 📟 Embedded System | active; entries carry a Glama badge → list on Glama first |
| 2 | wong2/awesome-mcp-servers | 4.4k | Community Servers | active (pushed Jul 2026) |
| 3 | wtsxDev/reverse-engineering | 10.6k | Dynamic Analysis | low activity (2023) — still worth one PR |
| 4 | tylerha97/awesome-reversing | 4.5k | Tools / Hardware | low activity (2023) |
| 5 | JoasASantos/Awesome-Hardware-and-IoT-Hacking | 0.4k | Tools | small but on-topic |
| 6 | vinta/awesome-python | 327k | Hardware | strict criteria (maturity/popularity) — wait until ~500★ |
| — | appcypher/awesome-mcp-servers, luong-komorebi/Awesome-Linux-Software | — | — | archived, skip |

### 1. punkpeye/awesome-mcp-servers
Line (Embedded System section, alphabetical):
```
- [emirmrkaljevic/usb-rea](https://github.com/emirmrkaljevic/usb-rea) [![emirmrkaljevic/usb-rea MCP server](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea/badges/score.svg)](https://glama.ai/mcp/servers/emirmrkaljevic/usb-rea) 🐍 🏠 🪟 🐧 - Reverse engineer USB gadgets: capture vendor-app traffic (usbmon/USBPcap), infer the protocol with frame-level evidence and generate a pyusb driver. Replay requires human confirmation.
```
PR title: `Add usb-rea (USB protocol reverse engineering)`
PR body: Adds usb-rea, an MCP server for reverse engineering Windows-only USB devices into open drivers. Python, local, MIT. Placed in Embedded System, alphabetical order.

### 2. wong2/awesome-mcp-servers
```
- **[usb-rea](https://github.com/emirmrkaljevic/usb-rea)** - Reverse engineer USB gadgets from captured traffic: per-action diffing, protocol inference with evidence, pyusb driver generation.
```

### 3. wtsxDev/reverse-engineering (Dynamic Analysis)
```
* [usb-rea](https://github.com/emirmrkaljevic/usb-rea) - Infers USB device protocols from labelled usbmon/USBPcap captures (values, lookup tables, counters, CRCs) and generates Python drivers
```
PR body: Open-source (MIT) tool for USB protocol reverse engineering from packet captures; fits Dynamic Analysis.

### 4. tylerha97/awesome-reversing — same line as #3, under the closest tools/hardware section.
### 5. Awesome-Hardware-and-IoT-Hacking — same line as #3 under Tools.
