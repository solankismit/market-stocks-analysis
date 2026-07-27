"""Daily ingestion entry point.

For each sector x timeframe: fetch fresh OHLC from TradingView (anonymous, no login),
compute RSI / RSI-based MA / ADX, classify, and upsert into stocks.db.
Falls back to the manually-exported CSVs in STOCKS ANALYSIS/ if the live fetch fails
(network issue, TradingView blocking anonymous access, library breakage, etc.).
"""

import logging
import sys
from datetime import datetime, timezone

import pandas as pd

import config
import db
import fetch_tv
import indicators
import seed_from_csv
from classify import classify_rsi

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(config.PROJECT_ROOT / "data" / "ingest.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("ingest")


def _rows_from_ohlc(sector, timeframe_key, ohlc, source):
    enriched = indicators.compute_all(ohlc)
    rows = []
    for date, row in enriched.iterrows():
        if pd.isna(row["rsi"]) or pd.isna(row["adx"]):
            continue
        rows.append({
            "sector": sector,
            "timeframe": timeframe_key,
            "date": date.strftime("%Y-%m-%d"),
            "open": row["open"],
            "close": row["close"],
            "rsi": row["rsi"],
            "rsi_ma": None if pd.isna(row["rsi_ma"]) else row["rsi_ma"],
            "adx": row["adx"],
            "classification": classify_rsi(row["rsi"]),
            "source": source,
        })
    return rows


def ingest_one(conn, sector, tv_symbol, tv_exchange, timeframe_key):
    try:
        ohlc = fetch_tv.fetch_ohlc(tv_symbol, tv_exchange, timeframe_key)
        rows = _rows_from_ohlc(sector, timeframe_key, ohlc, source="tvdatafeed")
        log.info("fetched %s %s via tvdatafeed: %d rows", sector, timeframe_key, len(rows))
    except Exception as exc:
        log.warning("tvdatafeed fetch failed for %s %s (%s) — falling back to CSV", sector, timeframe_key, exc)
        try:
            ohlc = seed_from_csv.load_ohlc_from_csv(tv_symbol, timeframe_key)
            rows = _rows_from_ohlc(sector, timeframe_key, ohlc, source="csv_fallback")
            log.info("loaded %s %s via CSV fallback: %d rows", sector, timeframe_key, len(rows))
        except Exception as csv_exc:
            log.error("CSV fallback also failed for %s %s: %s", sector, timeframe_key, csv_exc)
            return 0

    db.upsert_rows(conn, rows)
    return len(rows)


def main():
    started = datetime.now(timezone.utc)
    log.info("=== ingest run started at %s ===", started.isoformat())
    conn = db.get_connection()
    total = 0
    for sector, (tv_symbol, tv_exchange) in config.SECTORS.items():
        for timeframe_key in config.TIMEFRAMES:
            total += ingest_one(conn, sector, tv_symbol, tv_exchange, timeframe_key)
    conn.close()
    log.info("=== ingest run finished, %d rows upserted ===", total)


if __name__ == "__main__":
    main()
