# Case study: Corsair Hydro H100i Platinum (1b1c:0c18)

**Honesty note.** This is not a capture from my own hardware. The packets were reconstructed from
liquidctl's open-source driver ([`hydro_platinum.py`](https://github.com/liquidctl/liquidctl/blob/main/liquidctl/driver/hydro_platinum.py)),
built exactly the way that driver frames them, and written to a pcap with `usb_rea.synth`. usb-rea was
then run on that pcap without being told anything about the protocol. The goal is to show what
usb-rea finds on a protocol with a rolling sequence number and a CRC, and to compare it field by
field with a driver the community already trusts. The whole run is a test in CI:
[`tests/test_case_hydro_platinum.py`](../tests/test_case_hydro_platinum.py).

## The "capture"

Two labelled actions, 12 interrupt OUT reports of 64 bytes, in the order a user would click them in
the vendor app:

* `fan1 50%`, `fan1 20%`, `fan1 100%`, `fan1 35%`, `fan1 80%`, `fan1 65%`, `fan1 50%`
* `pump mode 0`, `pump mode 2`, `pump mode 1`, `pump mode 0`, `pump mode 2`

The sequence number advances on every report, as in liquidctl.

## What usb-rea recovered vs. the reference

| Byte | usb-rea output | liquidctl `hydro_platinum.py` |
|---|---|---|
| 0 | const `0x3f` | `_WRITE_PREFIX = 0x3f` |
| 1 | counter, +8 per message | `next(self._sequence) << 3` (feature bits 0b000) |
| 2 | const `0x14` | `_CMD_SET_COOLING = 0x14` |
| 11 / 17 | const `0x02` | fan mode `FIXED_DUTY = 0x2` |
| 16 | value, scale 2.55 (`fan1`) | fan1 duty, `fraction_of_byte(percentage=duty)` |
| 23 | value, scale 1 (`pump mode`) | `_PUMP_MODE_OFFSET` (quiet/balanced/extreme = 0/1/2) |
| 29 | const `0x07` | `_PROFILE_LENGTH = 7` |
| 63 | checksum `crc8` over bytes 1..62 | `mkCrcFun('crc-8')(buf[2:-1])` (poly 0x07; liquidctl's `buf[0]` is the HID report id, so its 2..-1 is our 1..62) |

Wire offsets are liquidctl's data offsets + 3.

## Check on values that were never captured

The command model usb-rea built encodes `fan1 42%` with sequence number 13, and `pump mode 2` with
sequence number 21. Both are byte-identical to what liquidctl's framing produces:

```
3f681400ff05ffffffffff02000000006b0200000000ff0100000000000700000000000000000000000000000000000000000000000000000000000000000041
```

(`fan1 42%`, seq 13: `0x68 = 13 << 3`, `0x6b = 107 = round(0.42 * 255)`, CRC8 `0x41`.)

## Limits found on the way

* With only one action the sequence byte is indistinguishable from a value that grows with the order
  of your clicks: usb-rea reports it as `unknown`, not as a counter. It needs at least two different
  actions in the capture to call it a counter. Record more than one action.
* The constant bytes (fan2 duty, profile area) are only "constant" because the capture never changed
  them. usb-rea says what it saw, not what the firmware accepts.
* Responses (the device's 64-byte status reply) are not part of this case study.

## Try it on your device

Have a Windows-only device? [Open a device request](https://github.com/emirmrkaljevic/usb-rea/discussions/1)
with a USBPcap capture and the list of what you clicked, and I will run it and publish the result.
