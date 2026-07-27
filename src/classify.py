"""Bucket a sector/timeframe RSI reading into whatever bands the user has configured
(see bands_store.py — fully dynamic, editable from the dashboard sidebar)."""

import bands_store


def classify_rsi(rsi):
    if rsi is None:
        return None
    return bands_store.classify(rsi)
