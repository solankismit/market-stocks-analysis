"""Single configurable ADX highlight threshold, persisted to data/adx_config.json.

Independent of the RSI bands — used to flag strong-trend readings (ADX above the
threshold) with their own highlight color, layered on top of the RSI band coloring.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADX_JSON = PROJECT_ROOT / "data" / "adx_config.json"

_DEFAULT = {"threshold": 20.0, "color": "#00bcd4"}


def load_config():
    if not ADX_JSON.exists():
        save_config(_DEFAULT["threshold"], _DEFAULT["color"])
        return dict(_DEFAULT)
    with open(ADX_JSON) as f:
        return json.load(f)


def save_config(threshold: float, color: str):
    ADX_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(ADX_JSON, "w") as f:
        json.dump({"threshold": float(threshold), "color": color}, f, indent=2)
