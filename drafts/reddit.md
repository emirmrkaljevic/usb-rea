<!-- DRAFTS — need Emir's OK; posted from Emir's Reddit account. Check each sub's self-promo rules first;
     space posts ≥1 day apart; never crosspost the same text. -->

## r/ReverseEngineering (link post)
**Title:** usb-rea: label your clicks in a vendor app, get the USB protocol (with frame-level evidence) and a pyusb driver
**Link:** https://github.com/emirmrkaljevic/usb-rea
**Comment:** Deterministic differ for usbmon/USBPcap captures: per-action byte diffing, linear 8/16-bit LE/BE fields with leave-one-out validation, lookup tables, rolling counters, sum/xor/CRC8/CRC16 detection. Every claim in the report cites frame numbers so you can check it in Wireshark. Validated against liquidctl's Kraken X and rivalcfg's Rival 100 protocols. Looking for hard captures that break it (multi-packet transactions, bitfields, encrypted stuff is out of scope).

## r/linux (text post; flair: Software Release if available)
**Title:** I made a tool to help write Linux drivers for USB gadgets that only have a Windows app
**Body:** RGB controllers, case LCDs, desk lamps… If the vendor only ships a Windows app, capture its USB traffic (USBPcap on Windows or usbmon in a VM passthrough), label each click, and usb-rea infers the protocol and generates a small Python/pyusb driver. Reverse engineering for interoperability is explicitly allowed in the EU (2009/24/EC art. 6) and US (DMCA 1201(f)). v0.1.0, MIT: https://github.com/emirmrkaljevic/usb-rea — no hardware needed for the demo (`usb-rea demo --device fan`). Feedback and captures very welcome.

## r/hardware — skip (no self-promo / software); use r/homelab or r/pcmasterrace? → **r/homelab** instead
**Title:** Tool for liberating Windows-only USB gadgets (fan controllers, LCDs, RGB) on Linux servers/desktops
**Body:** same as r/linux, shortened; lead with the fan controller GIF.

## r/OpenRGB
**Title:** usb-rea: semi-automatic protocol capture → driver for unsupported RGB devices
**Body:** For devices OpenRGB doesn't support yet: capture the vendor app, label colors (`color 255 0 0`), usb-rea finds which bytes carry R/G/B, command ids and checksums, and generates a Python driver you can port into an OpenRGB controller. Happy to help port a first device if someone shares a capture.

## r/LocalLLaMA
**Title:** MCP server that lets your local agent reverse engineer USB devices (with evidence, no hallucinated protocols)
**Body:** usb-rea exposes capture_start/stop, mark_action, diff_actions, report, scaffold_driver and replay_packet (needs human confirmation). The inference is deterministic; the model just orchestrates and explains. Works with any MCP client.
