# FAQ

## How is this different from Wireshark?

Wireshark, tshark and USBPcap capture USB traffic and dissect packets. usb-rea reads those captures (pcap or pcapng, from usbmon or USBPcap) and does the next step: it infers the command and protocol structure from labelled actions, then writes a Markdown report and a standalone pyusb driver. The same tools run as a headless CLI or as an MCP server (`usb-rea mcp`). It can also emit a Wireshark Lua dissector for the protocol it inferred, so you can keep using Wireshark on later captures.

The CLI and the inference details are in [usage](usage.md). MCP setup is in [mcp](mcp.md).

## Can I try it without hardware?

Yes. `pip install usb-rea && usb-rea demo --device fan` writes a synthetic capture, recovers the protocol, and generates a driver. `--device lamp` is a simpler 8-bit device; `--device lcd` is a pump cap screen; `--device dial` shows 32-bit values and packed bitfields.

## I only have a Windows vendor app

Capture with USBPcap or Wireshark, click each action with a short pause in between, then pass the actions in order with `--labels`. Markers with timestamps are better when you have them, and are required for handshake detection. If you cannot run usb-rea yourself, [open a device request](https://github.com/emirmrkaljevic/usb-rea/discussions/1) with a capture and I will run it and publish the result.

## Has someone already reverse engineered this device?

`usb-rea lookup 1e71:170e` (or the `ID 1e71:170e` form from `lsusb`, or a capture file) checks a VID:PID against an offline table of devices whose protocol an open-source project already implements. `--online` also asks [OpenDeviceDB](https://opendevicedb.org) (only the ID is sent, never the capture). The table is in [known devices](known-devices.md). A matching USB ID alone does not prove your unit speaks the same protocol; check the project's notes.

## What has been validated?

Synthetic devices, protocols documented by liquidctl and rivalcfg, public Wireshark captures, and a real AIO cooler LCD capture a user shared, where it found the same brightness command and image stream format the user had worked out by hand. Proof runs in CI: [validation](VALIDATION.md). Walk-throughs with a CRC8 and a rolling counter, and with a real Windows USBPcap of an ASUS TUF Gaming LC III LCD, are in the [Hydro Platinum](case-study-hydro-platinum.md) and [TUF LC III](case-study-asus-tuf-lc3.md) case studies.

## Is this legal?

Reverse engineering for interoperability is permitted (EU Directive 2009/24/EC Art. 6, US DMCA §1201(f)). usb-rea only analyzes traffic of devices you own and never redistributes vendor code.

