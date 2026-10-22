## drivers/ds1307.py — годинник DS1307 або DS3231 (адреса 0x68, однакові регістри часу)
import utime


class DS1307:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr

    @staticmethod
    def _bcd2bin(v):
        return (v & 0x0F) + ((v >> 4) * 10)

    @staticmethod
    def _bin2bcd(v):
        return ((v // 10) << 4) | (v % 10)

    def get_time(self):
        """(рік, міс, день, год, хв, сек, день_тижня 0=пн, 0) або None, якщо немає/не йде."""
        try:
            d = self.i2c.readfrom_mem(self.addr, 0, 7)
        except OSError:
            return None
        if d[0] & 0x80:                       # біт CH: годинник DS1307 зупинено
            return None
        sec = self._bcd2bin(d[0] & 0x7F)
        minute = self._bcd2bin(d[1])
        hour = self._bcd2bin(d[2] & 0x3F)     # 24-годинний режим
        day = self._bcd2bin(d[4])
        month = self._bcd2bin(d[5] & 0x1F)
        year = self._bcd2bin(d[6]) + 2000
        if not (1 <= month <= 12 and 1 <= day <= 31 and hour < 24 and minute < 60 and sec < 60):
            return None
        wd = utime.localtime(utime.mktime((year, month, day, 0, 0, 0, 0, 0)))[6]
        return (year, month, day, hour, minute, sec, wd, 0)

    def set_time(self, year, month, day, hour, minute, second):
        try:
            wd = utime.localtime(utime.mktime((year, month, day, 0, 0, 0, 0, 0)))[6]
            data = bytearray(7)
            data[0] = self._bin2bcd(second) & 0x7F     # CH = 0, годинник іде
            data[1] = self._bin2bcd(minute)
            data[2] = self._bin2bcd(hour)              # біт 6 = 0, 24-годинний режим
            data[3] = wd + 1
            data[4] = self._bin2bcd(day)
            data[5] = self._bin2bcd(month)
            data[6] = self._bin2bcd(year - 2000)
            self.i2c.writeto_mem(self.addr, 0, data)
            return True
        except OSError:
            return False