"""Checksum / CRC algorithms usb-rea can recognise. Self-contained: copied verbatim into generated drivers."""


def _crc(data, width, poly, init, refin, refout, xorout):
    top, mask = 1 << (width - 1), (1 << width) - 1
    crc = init
    for byte in data:
        if refin:
            byte = int("{:08b}".format(byte)[::-1], 2)
        crc ^= byte << (width - 8)
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & mask if crc & top else (crc << 1) & mask
    if refout:
        crc = int("{:0{w}b}".format(crc, w=width)[::-1], 2)
    return crc ^ xorout


def _xor(data):
    x = 0
    for c in data:
        x ^= c
    return x


# name -> (width in bytes, function)
CHECKSUMS = {
    "sum8": (1, lambda b: sum(b) & 0xFF),
    "xor8": (1, _xor),
    "neg_sum8": (1, lambda b: (-sum(b)) & 0xFF),
    "inv_sum8": (1, lambda b: (~sum(b)) & 0xFF),
    "crc8": (1, lambda b: _crc(b, 8, 0x07, 0x00, False, False, 0x00)),
    "crc8_maxim": (1, lambda b: _crc(b, 8, 0x31, 0x00, True, True, 0x00)),
    "sum16": (2, lambda b: sum(b) & 0xFFFF),
    "crc16_ccitt_false": (2, lambda b: _crc(b, 16, 0x1021, 0xFFFF, False, False, 0x0000)),
    "crc16_xmodem": (2, lambda b: _crc(b, 16, 0x1021, 0x0000, False, False, 0x0000)),
    "crc16_modbus": (2, lambda b: _crc(b, 16, 0x8005, 0xFFFF, True, True, 0x0000)),
    "crc16_kermit": (2, lambda b: _crc(b, 16, 0x1021, 0x0000, True, True, 0x0000)),
}


def compute(algo, data):
    return CHECKSUMS[algo][1](bytes(data))


def width(algo):
    return CHECKSUMS[algo][0]
