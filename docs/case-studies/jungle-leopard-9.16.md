# Case study: Jungle Leopard HD 9.16" panel (33c3:7788)

**Honesty note.** This is a pair of real Windows USBPcap captures of a Jungle Leopard HD 9.16"
panel, shared on [InfoPanel issue #4](https://github.com/emaspa/infopanel-1/issues/4). I ran both
through usb-rea and compared the result with `JL-PROTOCOL.md` in that project. The captures are
not stored in this repository: they are large, and the JPEG frames are whatever was on the
screen. This write-up is not a CI test and not a full driver. The same findings are on the
issue, in [this comment](https://github.com/emaspa/infopanel-1/issues/4#issuecomment-7033987400).
A device uid present in the info reply is omitted here.

## The capture

The panel enumerates as a CDC serial port with `VID_33C3&PID_7788`, the same USB ID as the
JL Chill Arc 360 (480x960). InfoPanel v1.4.0-preview.3.30 therefore detected it as that 480x960
cooler display. Enabling the panel failed with `getDeviceInfo failed` (`Display is not running.
Check the COM port and connection.`). The unit is sold as a 1920x480 screen.

The owner posted two captures, filtered to this device:

* `jl_916_boot.pcapng`: startup until the first frame appears
* `jl_916_brightness.pcapng`: brightness changed 0% to 50% to 100%

## What usb-rea recovered

The serial framing is the same as on the Chill Arc: `55 AA`, little-endian length, command byte,
then a u16 little-endian checksum. Two things differ on this 9.16" unit, and the first one
explains the `getDeviceInfo failed` error.

### 1. The 0x06 reply has no `status` field

The panel answers the getDeviceInfo command (367 bytes, checksum valid), but the JSON is wrapped
like this:

```
{"cmd":"info","data":{"uid":"...","width":1920,"height":462,"diplay_on":true,"brightness":95,"i_blocks":204560,...,"model":"D215-FL7707N-9.16inch-hor","version":"2.2","region":"",...}}
```

InfoPanel's `JlPanelDeviceTask` checks `info.Status != 200`, so this reply is rejected and the
handshake retries forever. Accepting `cmd == "info"` and reading width and height from `data`
should get it past the handshake. The panel reports **1920x462**, not 480, and the key really is
spelled `diplay_on`.

### 2. Firmware 2.2 sends raw JPEGs, with no size wrapper

Firmware 2.2 is below the 2.8 envelope cutoff used by later Jungle Leopard panels, and the
capture matches that: after the handshake the app writes raw JPEGs (`FF D8 FF E0 ... JFIF`)
straight to bulk OUT, with no 4-byte size prefix. This variant needs the pre-2.8 path (raw JPEG
per frame), not the envelope.

Boot sequence from `jl_916_boot.pcapng`, after SET_LINE_CODING at 2,000,000 baud:

```
FF D9 FF D9, then 00 00 00 00 pipeline reset
55 AA 07 00 06 0C 01 getDeviceInfo -> JSON above
55 AA 08 00 03 5F 69 01 setLight 95 -> 55 AA 08 00 03 00 0A 01 (ok)
55 AA 07 00 11 17 01 refresh -> 55 AA 08 00 11 00 18 01
raw JPEG frames, one 0x11 roughly every 45 frames
```

## Limits found on the way

* `jl_916_brightness.pcapng` has no 0x03 frames at all, only 0x11 and 1439 JPEGs, so either the
  app dims the rendered image during live mode instead of the backlight, or the slider change
  happened outside the capture. I could not settle which from these files.
* USBPcap cut every JPEG transfer at 65508 bytes, so I cannot see how a frame ends. A recapture
  with a larger snapshot length would show whether frames are followed by `FF D9 FF D9`.
* The captures are not in this repo, so this case study is a record of the analysis, not a
  regression test.

## Try it

Have a Windows-only device? [Open a device request](https://github.com/emirmrkaljevic/usb-rea/discussions/1)
with a USBPcap capture and the list of what you clicked, and I will run it and publish the result.
