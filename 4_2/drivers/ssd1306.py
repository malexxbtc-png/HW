# drivers/ssd1306.py
import framebuf

class SSD1306(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        for cmd in (
            0xAE,        # display off
            0xD5, 0x80,  # set display clock divide ratio/oscillator frequency
            0xA8, self.height - 1, # set multiplex ratio
            0xD3, 0x00,  # set display offset
            0x40,        # set start line
            0x8D, 0x14 if not self.external_vcc else 0x10, # charge pump
            0x20, 0x00,  # memory mode
            0xA1,        # seg remap
            0xC8,        # com scan dec
            0xDA, 0x12 if self.height == 64 else 0x02, # set com pins
            0x81, 0xCF,  # set contrast
            0xD9, 0xF1 if not self.external_vcc else 0x22, # pre-charge
            0xDB, 0x40,  # vcom deselect level
            0xA4,        # display all on resume
            0xA6,        # normal display
            0xAF,        # display on
        ):
            self.write_cmd(cmd)
        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(0xAE)

    def poweron(self):
        self.write_cmd(0xAF)

    def contrast(self, contrast):
        self.write_cmd(0x81)
        self.write_cmd(contrast)

    def invert(self, invert):
        self.write_cmd(0xA6 | (invert & 1))

    def show(self):
        x0 = 0
        x1 = self.width - 1
        if self.width == 64:
            x0 += 32
            x1 += 32
        self.write_cmd(0x21)
        self.write_cmd(x0)
        self.write_cmd(x1)
        self.write_cmd(0x22)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)


class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        self.write_list = [b'\x40', None]
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80  # Co = 1, D/C# = 0
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        self.write_list[1] = buf
        self.i2c.writeto(self.addr, b''.join(self.write_list))