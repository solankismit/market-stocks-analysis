"""Anonymous (no-login) OHLCV fetch from TradingView via tvDatafeed."""

import os

import certifi
import pandas as pd

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from tvDatafeed import Interval, TvDatafeed  # noqa: E402

import config  # noqa: E402

_INTERVAL_MAP = {
    "in_daily": Interval.in_daily,
    "in_weekly": Interval.in_weekly,
    "in_monthly": Interval.in_monthly,
}

_tv = None


def _client():
    global _tv
    if _tv is None:
        _tv = TvDatafeed()
    return _tv


def fetch_ohlc(tv_symbol: str, tv_exchange: str, timeframe_key: str) -> pd.DataFrame:
    """Returns a DataFrame indexed by date (ascending) with open/high/low/close/volume,
    or raises on failure (caller decides whether to fall back to CSVs)."""
    tf = config.TIMEFRAMES[timeframe_key]
    df = _client().get_hist(
        symbol=tv_symbol,
        exchange=tv_exchange,
        interval=_INTERVAL_MAP[tf["interval"]],
        n_bars=tf["n_bars"],
    )
    if df is None or df.empty:
        raise RuntimeError(f"tvDatafeed returned no data for {tv_exchange}:{tv_symbol} {timeframe_key}")
    df.index = df.index.normalize()
    df.index.name = "date"
    return df[["open", "high", "low", "close"]]
