# alerts.py — правила тривог (GSM немає, SMS не використовуємо)
import math


def dewpoint(t, rh):
    """Точка роси за формулою Магнуса, °C."""
    rh = max(min(rh, 100.0), 0.01)
    b, c = 17.62, 243.12
    g = math.log(rh / 100.0) + (b * t) / (c + t)
    return c * g / (b - g)


class AlertManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self._state = {}     # стан гістерезису по іменах

    def _hyst(self, name, value, on, off):
        """True, коли value піднялось до on; скидається лише нижче off."""
        active = self._state.get(name, False)
        active = (value >= off) if active else (value >= on)
        self._state[name] = active
        return active

    def check_alerts(self, stm, tilt, shock, wx, wx_age_min):
        """
        stm   — dict від STM32 (T, RH, Td, ...) або None
        tilt  — кут нахилу, градуси, або None
        shock — пік прискорення, або None
        wx    — останнє повідомлення "wx" від ESP або None
        Повертає список: wind, rain, snow, fog, ice, tilt, shock.
        """
        c = self.cfg
        alerts = []

        cur = {}
        if wx and wx_age_min < c.WX_MAX_AGE_MIN:
            cur = wx.get("cur") or {}

        # --- Вітер, дощ, сніг з Open-Meteo ---
        rain = snow = 0.0
        if cur:
            w = cur.get("w") or 0.0
            g = cur.get("g") or 0.0
            wind_a = self._hyst("wind_avg", w, c.WIND_AVG_ALERT, c.WIND_AVG_ALERT - c.WIND_HYST)
            wind_g = self._hyst("wind_gust", g, c.WIND_GUST_ALERT, c.WIND_GUST_ALERT - c.WIND_HYST)
            if wind_a or wind_g:
                alerts.append("wind")

            rain = cur.get("rain") or 0.0
            snow = cur.get("snow") or 0.0
            if snow >= c.SNOW_ALERT_CM:
                alerts.append("snow")
            elif rain >= c.RAIN_ALERT_MM:
                alerts.append("rain")

        # --- Локальні T, RH, Td ---
        t = rh = td = None
        if stm:
            t = stm.get("T")
            rh = stm.get("RH")
            td = stm.get("Td")
        if rh is None and cur:
            rh = cur.get("RH")                  # резерв, якщо BMP280 без вологості
        if td is None and t is not None and rh is not None:
            td = dewpoint(t, rh)

        # --- Туман: RH > 95 % і T - Td < 1 °C ---
        if t is not None and rh is not None and td is not None:
            humid = self._hyst("fog_rh", rh, c.FOG_RH_ON, c.FOG_RH_OFF)
            if humid and (t - td) < c.FOG_DEW_SPREAD:
                alerts.append("fog")

        # --- Ожеледь: T від -2 до +1 °C і (висока вологість або опади) ---
        if t is not None and c.ICE_T_MIN <= t <= c.ICE_T_MAX:
            wet = (rh is not None and rh >= c.ICE_RH) or rain >= c.RAIN_ALERT_MM or snow >= c.SNOW_ALERT_CM
            if wet:
                alerts.append("ice")

        # --- MPU6050 (може бути None при помилці читання) ---
        if tilt is not None and tilt > c.TILT_LIMIT_DEG:
            alerts.append("tilt")
        if shock is not None and shock > c.SHOCK_THRESHOLD:
            alerts.append("shock")

        return alerts