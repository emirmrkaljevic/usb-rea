---
title: "I built an agent tool that writes Linux drivers for Windows-only USB gadgets"
published: false
tags: linux, reverseengineering, python, opensource
---

<!-- DRAFT for Emir's review. Not published. Add the demo GIF before posting. -->

Every desk has one: an RGB controller, a PC-case LCD, a "smart" lamp that only works with a Windows vendor app. On Linux it's a paperweight.

The usual fix is hours in Wireshark: click a slider, stare at hex, click again, diff by eye. I automated that loop.

**usb-rea** (https://github.com/emirmrkaljevic/usb-rea):

1. captures USB traffic (usbmon on Linux, USBPcap on Windows),
2. lets you label each click (`usb-rea mark "brightness 50%"`),
3. diffs packets per action and finds constant headers, command bytes, value scaling and checksums,
4. writes a report where **every claim points to the exact Wireshark frame**,
5. generates a standalone Python/pyusb driver.

It also runs as an MCP server, so an AI agent can drive the whole session while you click.

```
$ usb-rea demo
brightness   100%  0xaa 0x01 round(value * 2.55 + 0) 0x00 sum8(bytes[0:4])
power         60%  0xaa 0x02 round(value * 1 + 0) 0x00 sum8(bytes[0:4])
hue          100%  0xaa 0x03 round(value * 0.5 + 0) 0x00 sum8(bytes[0:4])
```

## Evidence over vibes
LLMs are great at guessing protocols and terrible at admitting they guessed. usb-rea's inference is deterministic: a byte is only called a "value" if a linear fit explains every sample, and only called a "checksum" if the algorithm reproduces it in every packet. Confidence drops when you give it fewer than 3 samples, and the report says so.

## Safety and legality
Replaying packets to hardware needs explicit confirmation (`--yes`, or `user_confirmed` in MCP). Reverse engineering for interoperability is allowed under EU Directive 2009/24/EC Art. 6 and US DMCA §1201(f). usb-rea only analyzes traffic from devices you own.

## What's next
Rolling counters, CRC8/16, 16-bit values, emulated-device CI, and validation against documented protocols (liquidctl, rivalcfg). If you have a Windows-only gadget, a capture plus action labels in an issue would really help.
