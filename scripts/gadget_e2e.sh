#!/usr/bin/env bash
# Emulated-device end-to-end test (EXPERIMENTAL, not run in CI yet).
#
# Needs a normal Linux kernel with dummy_hcd, libcomposite (usb_f_hid) and usbmon, plus root.
# Creates a virtual HID "lamp" on dummy_hcd via configfs, captures real kernel USB traffic with
# usbmon while writing lamp commands to it, runs usb-rea on the capture, and checks that the
# device side received exactly what the generated driver would send.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "run as root"; exit 1; }
command -v dumpcap >/dev/null || { echo "need dumpcap (apt install tshark)"; exit 1; }
modprobe dummy_hcd libcomposite usbmon

G=/sys/kernel/config/usb_gadget/usbrea_lamp
cleanup() {
  [[ -n "${CAP_PID:-}" ]] && kill "$CAP_PID" 2>/dev/null || true
  if [[ -d $G ]]; then
    echo "" > $G/UDC 2>/dev/null || true
    rm -f $G/configs/c.1/hid.usb0; rmdir $G/configs/c.1/strings/0x409 $G/configs/c.1 \
      $G/functions/hid.usb0 $G/strings/0x409 $G 2>/dev/null || true
  fi
}
trap cleanup EXIT

mkdir -p $G && cd $G
echo 0x1234 > idVendor; echo 0xabcd > idProduct
mkdir -p strings/0x409; echo usb-rea > strings/0x409/manufacturer; echo "Fake Lamp" > strings/0x409/product
mkdir -p functions/hid.usb0
echo 0 > functions/hid.usb0/protocol; echo 0 > functions/hid.usb0/subclass; echo 5 > functions/hid.usb0/report_length
# vendor-defined report: 5 bytes in, 5 bytes out
printf '\x06\x00\xff\x09\x01\xa1\x01\x15\x00\x26\xff\x00\x75\x08\x95\x05\x09\x01\x81\x02\x95\x05\x09\x01\x91\x02\xc0' \
  > functions/hid.usb0/report_desc
mkdir -p configs/c.1/strings/0x409; echo lamp > configs/c.1/strings/0x409/configuration
ln -s functions/hid.usb0 configs/c.1/
UDC=$(ls /sys/class/udc | grep dummy | head -1); echo "$UDC" > UDC
sleep 1
cd - >/dev/null

BUS=$(for d in /sys/bus/usb/devices/*; do [[ -f $d/idVendor && $(cat $d/idVendor) == 1234 ]] && cat $d/busnum; done | head -1)
HIDRAW=/dev/$(ls /sys/class/hidraw | while read h; do grep -q 1234 /sys/class/hidraw/$h/device/uevent 2>/dev/null && echo $h; done | head -1)
OUT=$(mktemp -d)
dumpcap -q -i usbmon$BUS -w $OUT/lamp.pcapng & CAP_PID=$!
sleep 1
cat /dev/hidg0 > $OUT/device_side.bin & READER=$!

python3 - "$HIDRAW" "$OUT" <<'PY'
import json, sys, time
from usb_rea.synth import encode
hidraw, out = sys.argv[1], sys.argv[2]
marks = []
with open(hidraw, "wb", buffering=0) as f:
    for label in ["brightness 0%", "brightness 30%", "brightness 60%", "brightness 100%",
                  "hue 0", "hue 90", "hue 300"]:
        name, val = label.split()[0], float(label.split()[1].rstrip("%"))
        start = time.time(); time.sleep(0.2)
        f.write(b"\x00" + encode(name, val))   # report id 0 + payload
        time.sleep(0.3); marks.append({"label": label, "start": start, "end": time.time()})
json.dump(marks, open(f"{out}/lamp.pcapng.actions.json", "w"))
PY
sleep 1; kill $CAP_PID; CAP_PID=; kill $READER || true
usb-rea report $OUT/lamp.pcapng -o $OUT/report.md
python3 - "$OUT" <<'PY'
import sys
from usb_rea.pipeline import analyze
from usb_rea.synth import encode
p = analyze(f"{sys.argv[1]}/lamp.pcapng")
c = {c.name: c for c in p.commands}
assert c["brightness"].encode(45) == encode("brightness", 45), c["brightness"].fields
assert c["hue"].encode(200) == encode("hue", 200)
print("gadget e2e OK:", sys.argv[1])
PY
