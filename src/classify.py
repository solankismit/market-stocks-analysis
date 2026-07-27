"""Bucket a sector/timeframe reading into Strong / Neutral / Weak based on RSI."""

import config


def classify_rsi(rsi):
    if rsi is None:
        return None
    if rsi > config.STRONG_THRESHOLD:
        return config.STRONG
    if rsi < config.WEAK_THRESHOLD:
        return config.WEAK
    return config.NEUTRAL
