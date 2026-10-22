# link_esp.py — UART-зв'язок Pico <-> ESP32 (неблокуючий)
#
# Формат рядка (обидва напрямки):   <JSON>*<CRC16 hex, 4 символи>\n
# CRC16-CCITT (poly 0x1021, init 0xFFFF) рахується від байтів JSON-рядка так, як вони передані.
import json
import utime
from machine import UART, Pin


def crc16_ccitt(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


class ESPLink:
    MAX_LINE = 1024

    def __init__(self, uart_id=0, tx=0, rx=1, irq_pin=2):
        self.uart = UART(uart_id, baudrate=115200, tx=Pin(tx), rx=Pin(rx),
                         rxbuf=1024, timeout=0)
        self.irq_pin = Pin(irq_pin, Pin.IN, Pin.PULL_DOWN)
        self._buf = bytearray()
        self.last_wx = None
        self.has_wx = False
        self.wx_timestamp = 0
        self.last_rx_ms = 0
        self.has_rx = False
        self.crc_errors = 0

    def send_json(self, payload):
        raw = json.dumps(payload).encode()
        self.uart.write(raw + ("*%04X\n" % crc16_ccitt(raw)).encode())

    def poll(self):
        """Читає все, що надійшло, повертає список розібраних повідомлень (dict)."""
        n = self.uart.any()
        if n:
            chunk = self.uart.read(n)
            if chunk:
                self._buf.extend(chunk)
                if len(self._buf) > 2 * self.MAX_LINE and self._buf.find(b"\n") < 0:
                    self._buf = bytearray()          # сміття без кінця рядка

        out = []
        while True:
            i = self._buf.find(b"\n")
            if i < 0:
                break
            line = bytes(self._buf[:i])
            self._buf = self._buf[i + 1:]
            msg = self._parse(line)
            if msg is not None:
                out.append(msg)
        return out

    def _parse(self, line):
        line = line.strip()
        k = line.rfind(b"*")
        if k < 0:
            self.crc_errors += 1
            return None
        body = line[:k]
        try:
            rc = int(line[k + 1:].decode(), 16)
        except ValueError:
            self.crc_errors += 1
            return None
        if crc16_ccitt(body) != rc:
            self.crc_errors += 1
            return None
        try:
            msg = json.loads(body)
        except ValueError:
            self.crc_errors += 1
            return None
        if not isinstance(msg, dict):
            return None

        self.last_rx_ms = utime.ticks_ms()
        self.has_rx = True
        if msg.get("t") == "wx":
            self.last_wx = msg
            self.wx_timestamp = self.last_rx_ms
            self.has_wx = True
        return msg

    def wx_age_min(self):
        if not self.has_wx:
            return 999
        return utime.ticks_diff(utime.ticks_ms(), self.wx_timestamp) // 60000

    def is_online(self, timeout_ms):
        if not self.has_rx:
            return False
        return utime.ticks_diff(utime.ticks_ms(), self.last_rx_ms) < timeout_ms