"""Mutable sector registry, persisted to data/sectors.json.

Lets the dashboard add/remove sectors at runtime without editing config.py.
Falls back to config.py's hardcoded SECTORS on first run.
"""

import json

import config

SECTORS_JSON = config.PROJECT_ROOT / "data" / "sectors.json"

_DEFAULTS = {
    "CNXMETAL": ["CNXMETAL", "NSE"],
    "CNXPHARMA": ["CNXPHARMA", "NSE"],
    "CNXAUTO": ["CNXAUTO", "NSE"],
    "BANKNIFTY": ["BANKNIFTY", "NSE"],
    "CNXENERGY": ["CNXENERGY", "NSE"],
    "CNXFMCG": ["CNXFMCG", "NSE"],
    "CNXIT": ["CNXIT", "NSE"],
    "CNXMEDIA": ["CNXMEDIA", "NSE"],
    "CNXPSUBANK": ["CNXPSUBANK", "NSE"],
    "CNXREALTY": ["CNXREALTY", "NSE"],
    "CNXINFRA": ["CNXINFRA", "NSE"],
    "CNXFINANCE": ["CNXFINANCE", "NSE"],
    "NIFTYPVTBANK": ["NIFTYPVTBANK", "NSE"],
    "CNXCOMMODITIES": ["CNXCOMMODITIES", "NSE"],
    "CNXCONSUMPTION": ["CNXCONSUMPTION", "NSE"],
    "CNXPSE": ["CNXPSE", "NSE"],
    "CNXSERVICE": ["CNXSERVICE", "NSE"],
}


def load_sectors():
    """Returns {sector_name: (tv_symbol, tv_exchange)}."""
    if not SECTORS_JSON.exists():
        save_sectors(_DEFAULTS)
        return {k: tuple(v) for k, v in _DEFAULTS.items()}
    with open(SECTORS_JSON) as f:
        data = json.load(f)
    return {k: tuple(v) for k, v in data.items()}


def save_sectors(sectors: dict):
    SECTORS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(SECTORS_JSON, "w") as f:
        json.dump({k: list(v) for k, v in sectors.items()}, f, indent=2, sort_keys=True)


def add_sector(name: str, tv_symbol: str, tv_exchange: str):
    sectors = load_sectors()
    sectors[name] = (tv_symbol, tv_exchange)
    save_sectors(sectors)
    return sectors


def remove_sector(name: str):
    sectors = load_sectors()
    sectors.pop(name, None)
    save_sectors(sectors)
    return sectors
