import pytest
from usb_rea.checksums import compute

# standard "check" values from the CRC catalogue (reveng) for b"123456789"
@pytest.mark.parametrize("algo,check", [
    ("crc8", 0xF4), ("crc8_maxim", 0xA1), ("crc16_ccitt_false", 0x29B1),
    ("crc16_xmodem", 0x31C3), ("crc16_modbus", 0x4B37), ("crc16_kermit", 0x2189),
])
def test_catalogue_check_values(algo, check):
    assert compute(algo, b"123456789") == check
