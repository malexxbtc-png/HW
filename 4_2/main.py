# drivers/ds1307.py
# main.py — Raspberry Pi Pico (master) метеостанції. Без SIM800L.
import sys
import uasyncio as asyncio
import utime
from machine import I2C, Pin, WDT, RTC

import config
from status import SystemStatus
from alert import AlertManager
from link_esp import ESPLink
from drivers.stm_i2c import STM32I2C
from drivers.mpu6050 import MPU6050
from drivers.pir import PIRSensor
from drivers.ssd1306 import SSD1306_I2C
from drivers.ds1307 import DS1307

utime.sleep(config.BOOT_DELAY_S)         # вікно для Ctrl+C в Thonny

status = SystemStatus()
alerts_mgr = AlertManager(config)
wdt = None
snap_last = {}                           # reason -> ticks_ms останнього запиту
last_time_sync = None


# ---------- Ініціалізація ----------
def make_i2c():
    return I2C(0, sda=Pin(config.I2C_SDA, pull=Pin.PULL_UP),
               scl=Pin(config.I2C_SCL, pull=Pin.PULL_UP), freq=config.I2C_FREQ)


def init_i2c():
    try:
        i2c = make_i2c()
        return i2c, i2c.scan()
    except Exception:
        scl = Pin(config.I2C_SCL, Pin.OUT)       # відновлення шини: 9 імпульсів SCL
        for _ in range(9):
            scl.value(1)
            utime.sleep_us(5)
            scl.value(0)
            utime.sleep_us(5)
        i2c = make_i2c()
        return i2c, []


def safe(name, factory):
    try:
        return factory()
    except Exception as e:
        print("INIT FAIL:", name, e)
        status.log_error("init " + name)
        return None


i2c, found = init_i2c()
print("I2C scan:", [hex(a) for a in found])
EXPECTED = (config.ADDR_SSD1306, config.ADDR_MPU6050, config.ADDR_DS1307, config.ADDR_STM32)
status.missing = [a for a in EXPECTED if a not in found]
if status.missing:
    print("НЕ ЗНАЙДЕНО на I2C:", [hex(a) for a in status.missing])

stm = safe("stm", lambda: STM32I2C(i2c, config.ADDR_STM32))
mpu = safe("mpu", lambda: MPU6050(i2c, config.ADDR_MPU6050))
rtc_ext = safe("rtc", lambda: DS1307(i2c, config.ADDR_DS1307))
pir = safe("pir", lambda: PIRSensor(config.PIN_PIR))
esp = safe("esp", lambda: ESPLink(uart_id=0, tx=config.PIN_ESP_TX, rx=config.PIN_ESP_RX,
                                  irq_pin=config.PIN_ESP_IRQ))
display = safe("oled", lambda: SSD1306_I2C(128, 64, i2c, addr=config.ADDR_SSD1306))


# ---------- Час ----------
def load_rtc():
    """Встановлює внутрішній RTC Pico з зовнішнього годинника, якщо він є."""
    if rtc_ext:
        t = rtc_ext.get_time()
        if t and t[0] >= 2024:
            RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
            status.time_src = "rtc"


def hhmm():
    t = utime.localtime()
    return "%02d:%02d" % (t[3], t[4])


def sync_time(epoch_local):
    """epoch_local = Unix-час ЛОКАЛЬНОЇ стіни (UTC + зсув Києва). Епоха MicroPython = 2000."""
    t = utime.gmtime(epoch_local - 946684800)
    RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
    if rtc_ext:
        rtc_ext.set_time(t[0], t[1], t[2], t[3], t[4], t[5])
    status.time_src = "esp"


load_rtc()


# ---------- Знімки ----------
def request_snap(reason, cooldown_s):
    if not esp or not status.esp_online:
        return False
    now = utime.ticks_ms()
    last = snap_last.get(reason)
    if last is not None and utime.ticks_diff(now, last) < cooldown_s * 1000:
        return False
    snap_last[reason] = now
    esp.send_json({"t": "snap", "reason": reason})
    status.last_snap_reason = reason
    return True


# ---------- Задачі ----------
async def task_wdt():
    while True:
        if wdt:
            wdt.feed()
        await asyncio.sleep_ms(1000)


async def task_stm():
    while True:
        if stm:
            data, err = stm.read_data()
            now = utime.ticks_ms()
            if err:
                status.stm_fail += 1
                status.log_error(err)
                if status.stm_fail >= 3:
                    status.stm_ok = False
            else:
                status.stm_fail = 0
                status.stm_data = data
                if data["hb"] != status.stm_hb:
                    status.stm_hb = data["hb"]
                    status.stm_hb_t = now
                status.stm_ok = utime.ticks_diff(now, status.stm_hb_t) < config.STM_HB_STALE_S * 1000
        await asyncio.sleep(config.STM_POLL_INTERVAL)


async def task_sensors():
    prev = []
    tick = 0
    peak_shock = 0.0
    tilt = None
    t_timer = utime.ticks_ms()
    while True:
        # MPU6050: кут нахилу і пік удару між перевірками тривог
        if mpu:
            try:
                tl, sh, err = mpu.get_accel_angles()
                if err:
                    status.log_error(str(err))
                    tl = sh = None
            except Exception:
                status.log_error("mpu")
                tl = sh = None
            if tl is not None:
                tilt = tl
            if sh is not None and sh > peak_shock:
                peak_shock = sh

        # PIR
        status.pir_state = False
        if pir and pir.check_and_clear():
            status.pir_state = True
            request_snap("motion", config.PIR_COOLDOWN_S)

        tick += 1
        if tick >= 5:                         # раз на ~1 с
            tick = 0
            wx = esp.last_wx if esp else None
            age = esp.wx_age_min() if esp else 999
            active = alerts_mgr.check_alerts(status.stm_data, tilt, peak_shock, wx, age)
            peak_shock = 0.0
            status.active_alerts = active

            new = [a for a in active if a not in prev]
            if new:
                reason = "shock" if "shock" in new else "alert"
                request_snap(reason, config.ALERT_SNAP_COOLDOWN_S)
            prev = active

            if utime.ticks_diff(utime.ticks_ms(), t_timer) >= config.SNAP_INTERVAL_MIN * 60000:
                t_timer = utime.ticks_ms()
                request_snap("timer", 0)

        await asyncio.sleep_ms(200)


async def task_esp():
    global last_time_sync
    t_send = utime.ticks_add(utime.ticks_ms(), -config.HEARTBEAT_INTERVAL * 1000)
    while True:
        if esp:
            for msg in esp.poll():
                kind = msg.get("t")
                if kind == "hb":
                    status.wifi_rssi = msg.get("wifi", 0)
                    status.cam_ok = msg.get("cam", 0)
                    status.sd_ok = msg.get("sd", 0)
                    status.tg_ok = msg.get("tg", 0)
                    status.wx_age = msg.get("wx_age", 999)
                elif kind == "time":
                    now = utime.ticks_ms()
                    due = (last_time_sync is None or
                           utime.ticks_diff(now, last_time_sync) > config.TIME_RESYNC_H * 3600000)
                    if due and msg.get("epoch"):
                        try:
                            sync_time(int(msg["epoch"]))
                            last_time_sync = now
                        except Exception:
                            status.log_error("time")
                elif kind == "snap_done":
                    if msg.get("ok"):
                        status.last_snap_time = hhmm()

            status.esp_online = esp.is_online(config.ESP_OFFLINE_S * 1000)

            now = utime.ticks_ms()
            if utime.ticks_diff(now, t_send) >= config.HEARTBEAT_INTERVAL * 1000:
                t_send = now
                d = status.stm_data or {}
                esp.send_json({
                    "t": "data",
                    "T": d.get("T"), "RH": d.get("RH"), "P": d.get("P"), "Td": d.get("Td"),
                    "alert": status.active_alerts,
                    "loc": [config.FIXED_LAT, config.FIXED_LON],
                    "sys": {"up": status.uptime_s(), "err": status.err_count,
                            "stm": int(status.stm_ok)},
                })
        await asyncio.sleep_ms(100)


async def task_oled():
    while True:
        if display:
            bad = not (status.stm_ok and status.esp_online)
            bg, fg = (1, 0) if bad else (0, 1)
            d = status.stm_data
            display.fill(bg)
            display.text("STM:%s ESP:%s" % ("OK" if status.stm_ok else "ERR",
                                            "ON" if status.esp_online else "OFF"), 0, 0, fg)
            display.text("CAM:%d SD:%d TG:%d" % (status.cam_ok, status.sd_ok, status.tg_ok), 0, 8, fg)
            wxa = "--" if status.wx_age >= 999 else str(status.wx_age)
            display.text("WiFi:%d WX:%sm" % (status.wifi_rssi, wxa), 0, 16, fg)
            display.text("%s PIR:%s %s" % (hhmm(), "!" if status.pir_state else "-",
                                           status.time_src[:3]), 0, 24, fg)
            display.text("Snap:%s" % status.last_snap_reason[:10], 0, 32, fg)
            display.text(",".join(status.active_alerts)[:16] if status.active_alerts else "no alerts", 0, 40, fg)
            if d:
                rh = "--" if d["RH"] is None else "%d" % d["RH"]
                display.text("T:%.1f H:%s" % (d["T"], rh), 0, 48, fg)
            else:
                display.text("no STM data", 0, 48, fg)
            display.text("Err:%d Up:%dm" % (status.err_count, status.uptime_s() // 60), 0, 56, fg)
            try:
                display.show()
            except OSError:
                status.log_error("oled")
        await asyncio.sleep_ms(500)


async def main():
    global wdt
    if config.WDT_ENABLED:
        wdt = WDT(timeout=8000)
    for coro in (task_wdt, task_stm, task_sensors, task_esp, task_oled):
        asyncio.create_task(coro())
    while True:
        await asyncio.sleep(1)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
except Exception as e:
    print("\n[CRITICAL]")
    sys.print_exception(e)