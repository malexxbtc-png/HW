## drivers/stm_i2c.py — читання метеовузла STM32 (I2C slave 0x30)
import struct


class STM32I2C:
    REG_WHO, REG_STATUS, REG_HB, REG_DATA = 0x00, 0x01, 0x02, 0x10

    def __init__(self, i2c, addr=0x30):
        self.i2c = i2c
        self.addr = addr

    @staticmethod
    def _crc8(data):
        c = 0
        for b in data:
            c ^= b
            for _ in range(8):
                c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
        return c

    def read_data(self):
        """Повертає (dict, None) або (None, 'текст помилки')."""
        try:
            status = self.i2c.readfrom_mem(self.addr, self.REG_STATUS, 1)[0]
            hb = self.i2c.readfrom_mem(self.addr, self.REG_HB, 1)[0]
            blk = self.i2c.readfrom_mem(self.addr, self.REG_DATA, 11)
        except OSError:
            return None, "stm: no ack"
        if self._crc8(blk[:10]) != blk[10]:
            return None, "stm: crc"
        if not (status & 0x01):
            return None, "stm: sensor"
        t, rh, p, td = struct.unpack('<hHIh', blk[:10])
        return {
            "T": t / 100,
            "RH": None if rh == 0xFFFF else rh / 100,
            "P": p / 100,                       # гПа
            "Td": None if td == -32768 else td / 100,
            "hb": hb,
            "has_rh": bool(status & 0x02),
        }, None