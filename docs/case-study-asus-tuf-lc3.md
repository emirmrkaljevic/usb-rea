# Case study: ASUS TUF Gaming LC III LCD (0b05:1c7b)

**Honesty note.** This is a real Windows USBPcap capture of an ASUS TUF Gaming LC III AIO with LCD
under the vendor app. The owner shared it in
[liquidctl#936](https://github.com/liquidctl/liquidctl/issues/936) and agreed to a trimmed copy being
kept as a test. The fixture is `tests/data/asus-tuf-lc3-lcd.pcap.gz` (provenance in
[`tests/data/SOURCES.md`](../tests/data/SOURCES.md)). JPEG image bytes are blanked; only headers and
the end marker remain. Timestamps are shifted and IRP ids are replaced. The whole run is a test in
CI: [`tests/test_user_capture_lc3.py`](../tests/test_user_capture_lc3.py). The same device also shows
up in [coolerdash#176](https://github.com/damachine/coolerdash/issues/176) as a support request.

## The capture

Three labelled brightness clicks, in the order a user would change them in the vendor app:

* `brightness 0`, `brightness 50`, `brightness 100`

The trimmed file keeps only this device's traffic: setup, the first frames, and frames around each
brightness change (589 packets). The continuous JPEG stream on another endpoint is still present
enough for usb-rea to recover its layout.

## What usb-rea recovered

Run on the fixture with those three labels (current output of `usb-rea report`):

### Brightness (interrupt EP 0x01)

| Byte | usb-rea output | What the capture shows |
|---|---|---|
| 0..3 | const `12 01 00 80` | fixed prefix on every brightness write |
| 4 | value, scale 1 (`brightness`) | percent: `0x00` / `0x32` / `0x64` for 0 / 50 / 100 |
| 5..439 | const `0x00` | padding to 440 bytes |

Channel: interrupt EP `0x01`. Length: 440 bytes. Confidence on the fixture: **60%** (see limits
below). Sample frames: 228 (`brightness 0`), 332 (`brightness 50`).

### JPEG stream (interrupt EP 0x03)

| Detail | usb-rea output |
|---|---|
| Endpoint | interrupt EP `0x03` |
| Format / size | JPEG, 320x320 |
| Frames kept | 24 (8 to 10 packets each, 220 packets in all) |
| Chunk | 1024 bytes per packet, last one padded |
| First-packet header | `08 nn 00 80` (`nn` = packets in the frame) |
| Next-packet header | `08 ii 00 00` (`ii` = packet index in the frame) |
| Ack | `08 81 00 …` (16 bytes) on EP `0x84`, counted per frame |

USBPcap puts the GET_DESCRIPTOR reply in the "complete" record (stage 3); usb-rea reads that, so
VID:PID comes out as `0b05:1c7b`.

These match what the capture owner worked out by hand in liquidctl#936 (brightness prefix and percent
byte, JPEG headers, ack `08 81`, 320x320).

## Limits found on the way

* The reported frame rate is about **0.2 fps**. That is a trim artefact: most frames were cut out.
  On the full capture the stream is far denser.
* Brightness confidence is **60%** because only two of the three labelled actions keep a clean
  440-byte write (`brightness 0` and `brightness 50`); one action sent a differently shaped
  transaction and was ignored, so the note says "fewer than 3 samples". On a denser capture with
  three clean writes it reaches 100%.
* Image content in the fixture is zeros, so nothing that depends on pixels is tested here. The
  headers, ack, brightness byte, and USBPcap stage-3 VID:PID are.
* Device replies other than the per-frame ack are not part of this case study (`responses` is empty;
  the acks stay with the stream).

## Try it

```bash
gunzip -c tests/data/asus-tuf-lc3-lcd.pcap.gz > lc3.pcap
usb-rea report lc3.pcap -l "brightness 0;brightness 50;brightness 100" -o lc3.md
```

Have a Windows-only device? [Open a device request](https://github.com/emirmrkaljevic/usb-rea/discussions/1)
with a USBPcap capture and the list of what you clicked, and I will run it and publish the result.
