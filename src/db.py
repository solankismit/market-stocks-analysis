"""SQLite schema + upsert helpers for sector indicator history."""

import sqlite3

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sector_data (
    sector TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    close REAL,
    rsi REAL,
    rsi_ma REAL,
    adx REAL,
    classification TEXT,
    source TEXT,
    PRIMARY KEY (sector, timeframe, date)
);
"""


def get_connection():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(SCHEMA)
    return conn


def upsert_rows(conn, rows):
    """rows: iterable of dicts with keys matching sector_data columns."""
    conn.executemany(
        """
        INSERT INTO sector_data (sector, timeframe, date, open, close, rsi, rsi_ma, adx, classification, source)
        VALUES (:sector, :timeframe, :date, :open, :close, :rsi, :rsi_ma, :adx, :classification, :source)
        ON CONFLICT(sector, timeframe, date) DO UPDATE SET
            open=excluded.open,
            close=excluded.close,
            rsi=excluded.rsi,
            rsi_ma=excluded.rsi_ma,
            adx=excluded.adx,
            classification=excluded.classification,
            source=excluded.source
        """,
        rows,
    )
    conn.commit()


def fetch_latest(conn, sector=None, timeframe=None):
    query = "SELECT * FROM sector_data"
    clauses = []
    params = []
    if sector:
        clauses.append("sector = ?")
        params.append(sector)
    if timeframe:
        clauses.append("timeframe = ?")
        params.append(timeframe)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY date"
    cur = conn.execute(query, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]
