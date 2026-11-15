# Capturing from a Windows VM on Linux

If your desktop runs Linux, you don't need a Windows machine to capture the vendor app. Run Windows in a virtual machine, pass the gadget through to it, and record the traffic on the Linux host with usbmon. The VM's USB requests still go through the host kernel, so usbmon sees every packet the vendor app sends.

## 1. Find the gadget's bus

```bash
lsusb
# Bus 003 Device 007: ID 1e71:170e NZXT ...
```

The bus number (3 here) is the usbmon interface you capture on, and the device number (7) is how you pick the gadget out of the capture later. `usb-rea lookup 1e71:170e` tells you whether another open-source project already speaks this protocol, before you spend time on a capture.

## 2. Pass the gadget through to the VM

- virt-manager / QEMU: open the VM details, Add Hardware, USB Host Device, and pick the gadget.
- VirtualBox: enable a USB 2.0 or 3.0 controller in the VM settings and add a USB device filter for it.

Install the vendor app inside Windows as usual and check that it finds the device.

## 3. Capture on the host

```bash
sudo modprobe usbmon
usb-rea capture start --bus 3 -o lamp.pcapng
```

Capturing one bus keeps the file small. Start the capture before you attach the gadget to the VM (or before the VM boots): the attach makes Windows read the descriptors again, and usb-rea reads the VID:PID and the HID report descriptor from them.

## 4. Click and mark

Because the capture runs on the host, you can mark each action right before you click it in the VM:

```bash
usb-rea mark -m lamp.pcapng.actions.json "brightness 0%"     # then click it in the vendor app
usb-rea mark -m lamp.pcapng.actions.json "brightness 50%"
usb-rea mark -m lamp.pcapng.actions.json "brightness 100%"
usb-rea capture stop
```

Step through at least three values per setting. Markers with timestamps are better than a plain list of labels, and handshake detection needs them.

## 5. Analyse

```bash
usb-rea transfers lamp.pcapng | head     # the "dev" column is the device number from lsusb
usb-rea report lamp.pcapng -d 7 -o report.md
usb-rea scaffold lamp.pcapng -d 7 -o lamp_driver.py
```

`-d` limits the analysis to one device, so a keyboard or webcam on the same bus doesn't add noise. Note that the device number changes every time the gadget is replugged or handed to the VM, so read it from the capture, not from an older `lsusb`.

When the generated driver works, detach the gadget from the VM and test it on the host.

## Before you share a capture

A capture contains the gadget's string descriptors, which can include its serial number, and the traffic of everything else on that bus. If you [open a device request](https://github.com/emirmrkaljevic/usb-rea/discussions/1), tell me if you want anything removed before results are published.
