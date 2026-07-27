"""Parse TradingView-exported CSVs in STOCKS ANALYSIS/ into OHLC DataFrames.

Used both as a one-time DB bootstrap and as ingest.py's fallback path when the
live tvDatafeed fetch fails.
"""

import pandas as pd

import config


def _csv_path(tv_symbol: str, timeframe_key: str):
    suffix = config.TIMEFRAMES[timeframe_key]["csv_suffix"]
    matches = list(config.CSV_DIR.glob(f"NSE_{tv_symbol}, {suffix}_*.csv"))
    return matches[0] if matches else None


def load_ohlc_from_csv(tv_symbol: str, timeframe_key: str) -> pd.DataFrame:
    path = _csv_path(tv_symbol, timeframe_key)
    if path is None:
        raise FileNotFoundError(f"No CSV found for {tv_symbol} {timeframe_key} in {config.CSV_DIR}")
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["time"])
    df = df.set_index("date").sort_index()
    return df[["open", "high", "low", "close"]]


if __name__ == "__main__":
    import db
    import indicators
    from classify import classify_rsi

    conn = db.get_connection()
    for sector, (tv_symbol, tv_exchange) in config.SECTORS.items():
        for timeframe_key in config.TIMEFRAMES:
            ohlc = load_ohlc_from_csv(tv_symbol, timeframe_key)
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
                    "source": "csv_seed",
                })
            db.upsert_rows(conn, rows)
            print(f"seeded {sector} {timeframe_key}: {len(rows)} rows")
    conn.close()
