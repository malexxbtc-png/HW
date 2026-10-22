# status.py — стан системи
import utime


class SystemStatus:
    def __init__(self):
        # STM32
        self.stm_ok = False
        self.stm_data = None            # dict з stm_i2c або None
        self.stm_hb = -1
        self.stm_hb_t = utime.ticks_ms()
        self.stm_fail = 0
        # ESP32
        self.esp_online = False
        self.cam_ok = 0
        self.sd_ok = 0
        self.tg_ok = 0
        self.wifi_rssi = 0
        self.wx_age = 999               # хв, значення від ESP
        # знімки, час
        self.last_snap_reason = "none"
        self.last_snap_time = "--:--"
        self.time_src = "none"          # none | rtc | esp
        # датчики
        self.pir_state = False
        self.active_alerts = []
        # OLED
        self.oled_fail = 0
        # лічильники проходів задач: якщо число не росте, задача зависла
        self.loops = {"hb": 0, "stm": 0, "sens": 0, "esp": 0, "oled": 0}
        # діагностика
        self.missing = []               # очікувані I2C-адреси, яких немає
        self.err_count = 0
        self.error_log = []             # останні 5 помилок
        self.boot_ms = utime.ticks_ms()

    def log_error(self, err_str):
        if len(self.error_log) >= 5:
            self.error_log.pop(0)
        self.error_log.append(err_str)
        self.err_count += 1

    def uptime_s(self):
        return utime.ticks_diff(utime.ticks_ms(), self.boot_ms) // 1000