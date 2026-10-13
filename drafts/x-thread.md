<!-- DRAFT for @hattAtdev — needs Emir's OK. Attach docs/demo.gif to tweet 1. -->

1/ Your RGB controller / case LCD / desk lamp only has a Windows app?

I built usb-rea: click around in the vendor app, it captures the USB traffic, figures out the protocol and writes an open Python driver. With receipts.

github.com/emirmrkaljevic/usb-rea [GIF]

2/ How: label each click ("fan 1200", "color 255 0 0"). usb-rea diffs the packets per action and finds:
• header + command ids
• 8/16-bit values (LE/BE)
• lookup tables
• rolling counters
• sum/xor/CRC8/CRC16 checksums

3/ Every claim in the report points to the exact Wireshark frame. No vibes: if a linear fit doesn't survive leave-one-out, it becomes a lookup table and the report tells you.

4/ It's also an MCP server. Your agent runs the capture, asks you to click, explains the protocol and generates the driver. Sending anything to the device always needs your OK.

5/ Validated on protocols documented by @liquidctl and rivalcfg + public Wireshark captures. v0.1.0, MIT, pure Python. Got a weird USB gadget? Send me a capture.
