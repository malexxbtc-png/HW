# drivers/mpu6050.py
import math

class MPU6050:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr
        self._init_sensor()

    def _init_sensor(self):
        try:
            self.i2c.writeto_mem(self.addr, 0x6B, b'\x00') # Wake up
            # Увімкнення переривання по руху (Motion Detection Interrupt)
            self.i2c.writeto_mem(self.addr, 0x38, b'\x40') # Interrupt enable: Motion
            self.i2c.writeto_mem(self.addr, 0x1F, b'\x10') # MOT_THR (пороги)
            self.i2c.writeto_mem(self.addr, 0x20, b'\x01') # MOT_DUR (тривалість)
        except Exception:
            pass

    def get_accel_angles(self):
        try:
            data = self.i2c.readfrom_mem(self.addr, 0x3B, 6)
            ax, ay, az = ustruct.unpack(">h h h", data)
            
            # Конвертація в g (приблизно для діапазону +-2g)
            ax_g = ax / 16384.0
            ay_g = ay / 16384.0
            az_g = az / 16384.0
            
            # Розрахунок кута нахилу (tilt)
            total_g = math.sqrt(ax_g**2 + ay_g**2 + az_g**2)
            if total_g == 0:
                total_g = 0.001
            tilt = math.acos(max(-1.0, min(1.0, az_g / total_g))) * 57.2958
            
            # Визначення сильного поштовху (shock)
            shock_val = abs(total_g - 1.0)
            
            return tilt, shock_val, None
        except Exception as e:
            return 0.0, 0.0, str(e)
import ustruct