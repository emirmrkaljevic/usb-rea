<!-- DRAFT — needs Emir's OK; posted from Emir's HN account. Best slot: Tue/Wed 15:00–16:00 CEST. -->

**Title (≤80 chars):**
Show HN: usb-rea – Turn Windows-only USB gadgets into open Python drivers

**URL:** https://github.com/emirmrkaljevic/usb-rea

**First comment (by author):**

Hi HN, I'm Emir. Most RGB controllers, case LCDs and "smart" desk gadgets only ship a Windows app. Writing a Linux driver normally means hours in Wireshark: click a slider, stare at hex, repeat.

usb-rea automates that loop:

1. capture USB traffic (usbmon on Linux, USBPcap on Windows),
2. label each click (`usb-rea mark "fan 1200"`),
3. it diffs packets per action and infers constants, command ids, 8/16-bit values (LE/BE), lookup tables, rolling counters and checksums (sum/xor/CRC8/CRC16),
4. it writes a report where every claim cites Wireshark frame numbers, plus a standalone pyusb driver.

It also runs as an MCP server, so an agent can drive the session while you click; sending anything to the device always needs explicit confirmation.

Inference is deterministic, not an LLM guess: a byte is only a "value" if a linear fit survives leave-one-out, otherwise it becomes a lookup table and the report says the table only covers captured values.

Honest status: v0.1.0, validated on synthetic devices, on protocols documented by liquidctl (Kraken X) and rivalcfg (Rival 100), and on public Wireshark captures. It has not yet been run on a physical gadget I own, so captures from your weird devices are the most useful feedback.

`pip install git+https://github.com/emirmrkaljevic/usb-rea && usb-rea demo --device fan` runs with no hardware.
