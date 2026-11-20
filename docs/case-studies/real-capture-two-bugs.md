# Case study: two bugs a real USBPcap capture found

**Honesty note.** This is the same trimmed ASUS TUF Gaming LC III capture as the
[LCD walk-through](asus-tuf-lc3.md): a real Windows USBPcap shared by the owner in
[liquidctl#936](https://github.com/liquidctl/liquidctl/issues/936), who agreed to a trimmed copy
being kept as a test. The fixture is `tests/data/asus-tuf-lc3-lcd.pcap.gz` (provenance in
[`tests/data/SOURCES.md`](../../tests/data/SOURCES.md)). JPEG image bytes are blanked; only headers
and the end marker remain. Timestamps are shifted and IRP ids are replaced. The whole run is a test
in CI: [`tests/test_user_capture_lc3.py`](../../tests/test_user_capture_lc3.py).

Until this file arrived, every test of usb-rea ran on captures I generated myself, on protocols
documented by liquidctl and rivalcfg, and on a few public Wireshark samples. All of that passed.
This capture found two bugs that none of those tests could have found, because they were about
how USBPcap writes files and about what a trim (or a pause in the video) does to ack counts.
Both were fixed in v0.7.6. A longer write-up is on
[dev.to](https://dev.to/emirmrkaljevic/what-a-real-users-usb-capture-found-that-my-synthetic-tests-didnt-two-bugs-in-usb-rea-57k).

## The capture

The owner recorded the LC III under the vendor app while changing screen brightness. The full
capture is about 76,000 packets, nearly all of them a 320x320 JPEG video the app streams to the
screen at around 70 frames per second, plus a few brightness writes hidden in between. After
image-stream detection landed in v0.7.4, the full capture already gave the right protocol
(brightness on EP 0x01, JPEG on EP 0x03, ack `08 81` on EP 0x84). The bugs showed up only when
that capture was turned into the trimmed fixture:

* only this device's packets are kept: the setup, the first 8 frames, and two frames on each side
  of each brightness change (589 packets, 6.5 KB gzipped)
* image data in every frame is zeroed, keeping the JPEG headers and the end marker
* timestamps are shifted to a fixed date and IRP ids are replaced with counters

The first run of the fixture test failed twice.

## Bug 1: USBPcap puts the control reply in the "complete" record

usb-rea finds the vendor and product id from the GET_DESCRIPTOR reply at the start of a capture.
On this file, v0.7.5 printed:

```
Device: `unknown (no GET_DESCRIPTOR in capture)`
```

The reply is in the file. `usb-rea transfers` on the fixture starts with:

```
     1 dev   2 ep 0x80 control   IN  8006000100001200 |
     2 dev   2 ep 0x80 control   IN  12 01 10 01 00 00 00 40 05 0b 7b 1c 51 00 01 02 03 01
```

USBPcap logs a control transfer in stages. Frame 1 is the setup stage (`80 06 00 01 ...`,
GET_DESCRIPTOR for the device descriptor). The descriptor itself (`12 01 ...`, with `05 0b 7b 1c`
being 0B05:1C7B little-endian) arrives in a separate record for the "complete" stage, stage 3.
The parser only took control IN data from the stage it expected, so on captures where the data
comes in stage 3 the descriptor was dropped. My own synthetic USBPcap files never did that, which
is why the tests never caught it.

v0.7.6 reads control IN data from the complete record too. Same file, new report:

```
Device: `0b05:1c7b`
```

## Bug 2: counting the ack over the whole capture

The second failure was quieter. v0.7.5 found the video stream and the brightness command, but no
frame ack. The `08 81` acks did not disappear: they ended up in the report as a "reply to
`brightness`", because a couple of them happened to arrive a few milliseconds after a brightness
write.

The old rule was: a fixed device-to-host message is the ack if it shows up about once per frame
over the whole capture (between 0.5x and 1.2x the number of frames). On the full capture that
held. On the trimmed one it did not: the fixture keeps the acks for frames that were cut out, so
it has 66 acks for 24 frames. That is an artefact of trimming, but the same thing happens on a
real capture whenever the app keeps polling while it pauses the video, and a global ratio cannot
tell the difference.

v0.7.6 counts the ack per frame instead: a fixed device-to-host message between one frame's start
and the next (and no more than 1 s after the frame's last packet). It is the ack when at least
half of the frames have one and most of those have exactly one. The `frames_acked` field says how
many frames it was seen for. The report now has this line in the stream section (real output on
the fixture):

```
- Ack: `08 81 00 00 00 00 00 00 00 00 00 00 00 00 00 00` on EP 0x84, 66x (frames 30, 52, 94, 116, 138)
```

Because the acks are set aside with the stream, the bogus "Reply to `brightness`" section is gone.
Summarised from the `usb-rea infer` JSON of both versions on the fixture, same labels:

```
0.7.5  vid/pid None None   ack None                     responses 1
0.7.6  vid/pid 2821 7291   ack EP 0x84, frames_acked 18 responses 0
```

(2821 and 7291 are 0x0B05 and 0x1C7B.)

## Limits found on the way

These numbers in the fixture report are about the trimming, not the device:

* The frame rate shows as about **0.2 fps**, because most frames were cut out. The full capture
  is around 70 fps.
* The brightness command comes out at **60%** confidence from two clean samples (`brightness 0`
  and `brightness 50`); the third action is ignored because it sent a differently shaped
  transaction. On the full capture it is 100%.
* The image content is zeros, so the fixture cannot test anything that depends on the pixels.

What it does test is everything the bugs were about: the device descriptor in a USBPcap complete
record, the stream headers, the per-frame ack, and the brightness byte on its own endpoint.

## Try it

```bash
gunzip -c tests/data/asus-tuf-lc3-lcd.pcap.gz > lc3.pcap
usb-rea report lc3.pcap -l "brightness 0;brightness 50;brightness 100" -o lc3.md
```

Have a Windows-only device? [Open a device request](https://github.com/emirmrkaljevic/usb-rea/discussions/1)
with a USBPcap capture and the list of what you clicked, and I will run it and publish the result.
