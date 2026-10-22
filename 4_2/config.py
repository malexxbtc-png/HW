## config.py — налаштування Pico (master)

# --- Налагодження ---
WDT_ENABLED = False          # увімкнути True, коли все стабільно працює
BOOT_DELAY_S = 3             # пауза на старті, щоб Thonny міг перервати (Ctrl+C)
ALERT_SNAP_COOLDOWN_S = 60   # не частіше 1 фото за тривогу на хвилину

# --- I2C0 ---
I2C_FREQ = 100_000
I2C_SDA = 4
I2C_SCL = 5

# --- Піни ---
PIN_ESP_TX = 0               # UART0 TX -> ESP32 GPIO18
PIN_ESP_RX = 1               # UART0 RX <- ESP32 GPIO17
PIN_ESP_IRQ = 2              # <- ESP32 GPIO16
PIN_PIR = 3                  # PIR AM312
PIN_MPU_INT = 6              # MPU6050 INT

# --- Адреси I2C ---
ADDR_SSD1306 = 0x3C
ADDR_MPU6050 = 0x69          # AD0 -> 3V3 (0x68 зайнято годинником)
ADDR_DS1307 = 0x68           # DS1307 або DS3231
ADDR_STM32 = 0x30

# --- Геолокація (GSM немає, координати фіксовані) ---
FIXED_LAT = 49.9884
FIXED_LON = 36.2328

# --- Інтервали ---
STM_POLL_INTERVAL = 2        # с
HEARTBEAT_INTERVAL = 5       # с, відправка "data" на ESP
SNAP_INTERVAL_MIN = 30       # фото за таймером
PIR_COOLDOWN_S = 30
ESP_OFFLINE_S = 15           # 3 пропущені heartbeat по 5 с
STM_HB_STALE_S = 6           # heartbeat STM не змінюється = завис
TIME_RESYNC_H = 6            # як часто підлаштовувати годинник з ESP

# --- Пороги тривог ---
TILT_LIMIT_DEG = 15.0
SHOCK_THRESHOLD = 2.5
WX_MAX_AGE_MIN = 120

WIND_AVG_ALERT = 10.0        # м/с, середній вітер
WIND_GUST_ALERT = 15.0       # м/с, пориви
WIND_HYST = 1.0
RAIN_ALERT_MM = 0.1          # мм/год (Open-Meteo precipitation)
SNOW_ALERT_CM = 0.1          # см/год (Open-Meteo snowfall)

FOG_RH_ON = 95.0
FOG_RH_OFF = 92.0
FOG_DEW_SPREAD = 1.0         # T - Td менше цього = туман

ICE_T_MIN = -2.0
ICE_T_MAX = 1.0
ICE_RH = 85.0