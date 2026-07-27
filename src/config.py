"""Central configuration: sectors, timeframes, indicator periods, classification thresholds."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "stocks.db"
CSV_DIR = PROJECT_ROOT / "STOCKS ANALYSIS"

# sector name -> (tv_symbol, tv_exchange), persisted in data/sectors.json so the
# dashboard can add/remove sectors at runtime (see sectors_store.py).
def _load_sectors():
    import sectors_store
    return sectors_store.load_sectors()


SECTORS = _load_sectors()

# timeframe key -> (tvDatafeed Interval name, n_bars to fetch, csv filename suffix)
TIMEFRAMES = {
    "1D": {"interval": "in_daily", "n_bars": 3000, "csv_suffix": "1D"},
    "1W": {"interval": "in_weekly", "n_bars": 1500, "csv_suffix": "1W"},
    "1M": {"interval": "in_monthly", "n_bars": 500, "csv_suffix": "1M"},
}

# TradingView default indicator settings
RSI_LENGTH = 14
RSI_MA_LENGTH = 14
ADX_LENGTH = 14
ADX_SMOOTHING = 14

# Classification bands (applied to RSI, primarily read on the Monthly timeframe)
STRONG_THRESHOLD = 60.0
WEAK_THRESHOLD = 40.0

STRONG = "Strong"
NEUTRAL = "Neutral"
WEAK = "Weak"
