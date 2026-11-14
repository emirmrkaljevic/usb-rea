# Capturing on Windows with USBPcap

Most gadgets usb-rea is meant for (case LCDs, RGB controllers, mice, lamps) only have a Windows app, so the capture usually happens on Windows. This page is the short version of how I do it. The analysis can then run anywhere: `pip install usb-rea` works on Windows too, or copy the file to a Linux box.

## 1. Install USBPcap

The Wireshark installer for Windows offers USBPcap as an optional component; tick it. You can also install it on its own from [desowin.org/usbpcap](https://desowin.org/usbpcap/). Reboot afterwards, the filter driver only loads at boot.

## 2. Find the right interface

Wireshark lists one `USBPcap1`, `USBPcap2`, ... interface per root hub. Click the gear icon next to each one: it shows the devices on that hub, so pick the hub your gadget is on and, if you like, tick only that device. Fewer devices means a cleaner capture (a USB keyboard or webcam on the same hub adds noise).

## 3. Capture the descriptors

usb-rea reads the VID:PID and the HID report descriptor from the GET_DESCRIPTOR requests in the capture. Either start the capture first and then unplug and replug the gadget, or enable "Inject already connected devices descriptors" in the USBPcap options. Without descriptors the protocol analysis still works, but `usb-rea lookup` and `usb-rea hid` have nothing to read.

## 4. Click slowly, one action at a time

Open the vendor app, then for every setting step through at least three values (brightness 0%, 50%, 100%; three colors; two fan speeds). Leave a pause of two or three seconds between clicks and write the actions down in order. usb-rea splits the traffic at the pauses and sets aside the app's own background polling, so you don't need to stop the capture between actions.

If you want to send a picture to a screen, do it once with a small, simple image; the [usage](usage.md#image-streams-pictures-and-video-sent-to-a-screen) page explains what usb-rea looks for.

## 5. Save and analyse

Stop the capture and save it as pcapng (pcap works too). Put your list of actions in a text file, one per line, then:

```bash
usb-rea lookup capture.pcapng                      # already documented by another project?
usb-rea report capture.pcapng --labels labels.txt -o report.md
usb-rea scaffold capture.pcapng --labels labels.txt -o driver.py
```

## Command line instead of Wireshark

`USBPcapCMD.exe` (in the USBPcap install folder) runs without a GUI. Run it from an admin prompt without arguments to pick the hub interactively, or for example:

```
USBPcapCMD.exe -d \\.\USBPcap1 -A -o capture.pcap
```

`-A` captures every device on that hub. Press Ctrl+C to stop.

## Before you share a capture

A capture contains the gadget's string descriptors, which can include its serial number, and everything else on the same hub while you recorded. Capture only the device you care about. If you [open a device request](https://github.com/emirmrkaljevic/usb-rea/discussions/1), tell me if you want anything removed before results are published.
