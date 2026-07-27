# Sector Strength Dashboard

Automated pipeline that fetches Daily/Weekly/Monthly OHLC for NSE sector indices
(CNXMETAL, CNXPHARMA today) straight from TradingView (no login needed), computes
RSI / RSI-based MA / ADX to match TradingView's own values exactly, classifies each
sector as Strong (RSI > 60) / Neutral (40-60) / Weak (< 40), and shows it all in an
interactive Streamlit dashboard.

## One-time setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Usage

Ingest fresh data (fetches from TradingView; falls back to the CSVs in
`STOCKS ANALYSIS/` if the fetch fails):

```bash
./.venv/bin/python3 src/ingest.py
```

Run the dashboard:

```bash
./.venv/bin/streamlit run dashboard/app.py
```

## Automate daily ingestion (macOS)

```bash
scripts/install_schedule.sh
```

Installs a launchd agent that runs `src/ingest.py` Mon-Fri at 18:00 local time.
Check status: `launchctl list | grep marketstocks`
Logs: `data/launchd.out.log`, `data/launchd.err.log`, `data/ingest.log`
Uninstall: `launchctl unload ~/Library/LaunchAgents/com.marketstocks.ingest.plist`

## Adding a sector

Add an entry to `SECTORS` in `src/config.py` with its TradingView symbol/exchange
(e.g. `"CNXAUTO": ("CNXAUTO", "NSE")`) — no other code changes needed.

## Adjusting thresholds

`STRONG_THRESHOLD` / `WEAK_THRESHOLD` in `src/config.py`.
