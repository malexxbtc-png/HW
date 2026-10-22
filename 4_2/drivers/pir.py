# drivers/pir.py
from machine import Pin

class PIRSensor:
    def __init__(self, pin_num=3):
        self.pin = Pin(pin_num, Pin.PULL_DOWN)
        self.motion_detected = False
        self.pin.irq(trigger=Pin.IRQ_RISING, handler=self._irq_handler)

    def _irq_handler(self, pin):
        self.motion_detected = True

    def check_and_clear(self):
        if self.motion_detected:
            self.motion_detected = False
            return True
        return False