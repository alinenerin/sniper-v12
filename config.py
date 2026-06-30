import os

IQ_EMAIL = os.environ.get("IQ_EMAIL", "laiane.aline@gmail.com")
IQ_PASSWORD = os.environ.get("IQ_PASSWORD", "alineegui95")
IQ_MODE = os.environ.get("IQ_MODE", "PRACTICE")

TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY", "1be0b948fb1c48bb997e350c542edafd")
POLYGON_KEY = os.environ.get("POLYGON_KEY", "gXySF0ojKao907z3vKOtpxr8opt0cbLx")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "d8p5sbpr01qp954vdn3gd8p5sbpr01qp954vdn40")

ENTRY_PERCENT = float(os.environ.get("ENTRY_PERCENT", "0.02"))
DAILY_STOP = int(os.environ.get("DAILY_STOP", "4"))
SEQ_STOP = int(os.environ.get("SEQ_STOP", "3"))
SEQ_PAUSE = int(os.environ.get("SEQ_PAUSE", "30"))
COOLDOWN = int(os.environ.get("COOLDOWN", "120"))
PORT = int(os.environ.get("PORT", "8080"))

OTC_PAIRS = os.environ.get("OTC_PAIRS", "EURUSD-OTC,GBPUSD-OTC,EURJPY-OTC,USDJPY-OTC,AUDUSD-OTC").split(",")
REAL_PAIRS = os.environ.get("REAL_PAIRS", "EURUSD,GBPUSD,EURJPY,USDJPY,AUDUSD").split(",")

# Channel settings
CHANNELS = {
    "OTC_M1": {"cycle": 57, "expiration": 1, "min_score": 150, "timeframe": 60},
    "OTC_M5": {"cycle": 290, "expiration": 5, "min_score": 160, "timeframe": 300},
    "REAL_M1": {"cycle": 57, "expiration": 1, "min_score": 70, "timeframe": 60},
    "REAL_M5": {"cycle": 290, "expiration": 5, "min_score": 75, "timeframe": 300},
}
