"""Mutable classification bands (Strong/Neutral/Weak, or however many the user wants),
persisted to data/bands.json.

Each band is {"name": str, "min": float, "color": "#hex"}. A value is classified into
the band with the greatest `min` that is <= the value — so bands only need a lower
bound each; the upper bound is implicitly "the next band's min" (or open-ended for the
top band). This lets the user add/remove/rename any number of bands freely.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BANDS_JSON = PROJECT_ROOT / "data" / "bands.json"

_DEFAULTS = [
    {"name": "Strong", "min": 60.0, "color": "#1a9850"},
    {"name": "Neutral", "min": 40.0, "color": "#e6b800"},
    {"name": "Weak", "min": 0.0, "color": "#d73027"},
]


def _sorted(bands):
    return sorted(bands, key=lambda b: b["min"])


def load_bands():
    if not BANDS_JSON.exists():
        save_bands(_DEFAULTS)
        return _sorted([dict(b) for b in _DEFAULTS])
    with open(BANDS_JSON) as f:
        data = json.load(f)
    return _sorted(data)


def save_bands(bands):
    BANDS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(BANDS_JSON, "w") as f:
        json.dump(_sorted(bands), f, indent=2)


def add_band(name: str, minimum: float, color: str):
    bands = [b for b in load_bands() if b["name"] != name]
    bands.append({"name": name, "min": float(minimum), "color": color})
    save_bands(bands)
    return bands


def classify(value, bands=None):
    """Returns the name of the band whose min is the greatest value <= `value`."""
    if value is None:
        return None
    bands = bands or load_bands()
    if not bands:
        return None
    ordered = _sorted(bands)
    chosen = ordered[0]
    for band in ordered:
        if value >= band["min"]:
            chosen = band
        else:
            break
    return chosen["name"]
