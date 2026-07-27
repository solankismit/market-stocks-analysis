"""RSI / RSI-based MA / ADX computed to match TradingView's Pine Script built-ins.

Reimplemented by hand (rather than relying on a generic TA library) so the smoothing
exactly matches Pine Script's `ta.rsi` / `ta.dmi` (Wilder's RMA), which is what the
CSVs exported from TradingView actually used.
"""

import pandas as pd

import config


def rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder's moving average (aka RMA): pine's ta.rma."""
    return series.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def rsi(close: pd.Series, length: int = config.RSI_LENGTH) -> pd.Series:
    change = close.diff()
    up = rma(change.clip(lower=0), length)
    down = rma(-change.clip(upper=0), length)
    rs = up / down
    return 100 - (100 / (1 + rs))


def rsi_ma(rsi_series: pd.Series, length: int = config.RSI_MA_LENGTH) -> pd.Series:
    """TradingView's built-in RSI indicator default MA type is SMA."""
    return rsi_series.rolling(window=length, min_periods=length).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series,
        di_length: int = config.ADX_LENGTH, adx_smoothing: int = config.ADX_SMOOTHING):
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(0.0, index=high.index)
    minus_dm = pd.Series(0.0, index=high.index)
    plus_mask = (up_move > down_move) & (up_move > 0)
    minus_mask = (down_move > up_move) & (down_move > 0)
    plus_dm[plus_mask] = up_move[plus_mask]
    minus_dm[minus_mask] = down_move[minus_mask]

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    tr_rma = rma(tr, di_length)
    plus_di = 100 * rma(plus_dm, di_length) / tr_rma
    minus_di = 100 * rma(minus_dm, di_length) / tr_rma

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx_line = rma(dx, adx_smoothing)
    return adx_line, plus_di, minus_di


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """df must have columns: open, high, low, close (indexed by date, ascending)."""
    out = df.copy()
    out["rsi"] = rsi(out["close"])
    out["rsi_ma"] = rsi_ma(out["rsi"])
    out["adx"], out["plus_di"], out["minus_di"] = adx(out["high"], out["low"], out["close"])
    return out
