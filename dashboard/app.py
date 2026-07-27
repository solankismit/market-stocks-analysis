"""Sector RSI classification dashboard — single board, all timeframes, configurable
thresholds/colors, and a Monthly-Weekly-Daily band-pattern filter.

Run with: streamlit run dashboard/app.py
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import adx_store  # noqa: E402
import bands_store  # noqa: E402
import config  # noqa: E402
import db  # noqa: E402
import fetch_tv  # noqa: E402
import sectors_store  # noqa: E402
from ingest import ingest_one  # noqa: E402

st.set_page_config(page_title="Sector Strength Dashboard", layout="wide")

st.markdown(
    """
    <style>
    .table-scroll {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        margin-bottom: 0.5rem;
    }
    .table-scroll table { border-collapse: collapse; }
    .table-scroll th, .table-scroll td {
        padding: 8px 14px;
        white-space: nowrap;
    }
    @media (max-width: 640px) {
        .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; }
        h1 { font-size: 1.5rem !important; }
        h3 { font-size: 1.1rem !important; }
        .table-scroll th, .table-scroll td {
            padding: 6px 10px;
            font-size: 0.82rem;
        }
        [data-testid="stCaptionContainer"] { font-size: 0.75rem; }
        div[data-testid="column"] { min-width: 100% !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

ANY = "Any"

tf_order = list(config.TIMEFRAMES.keys())
tf_names = {"1D": "Daily", "1W": "Weekly", "1M": "Monthly"}
tf_short = {"1D": "D", "1W": "W", "1M": "M"}


@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect(config.DB_PATH)
    df = pd.read_sql("SELECT * FROM sector_data", conn, parse_dates=["date"])
    conn.close()
    return df


# ---------------------------------------------------------------------------
# Sidebar: search & manage sectors
# ---------------------------------------------------------------------------
st.sidebar.header("Manage sectors")

active_sectors = sectors_store.load_sectors()

with st.sidebar.form("add_sector_form", clear_on_submit=True):
    st.caption("Search a TradingView symbol (NSE index/stock) and add it.")
    new_symbol = st.text_input("TradingView symbol", placeholder="e.g. CNXAUTO, BANKNIFTY, RELIANCE").strip().upper()
    new_exchange = st.text_input("Exchange", value="NSE").strip().upper()
    new_name = st.text_input("Display name (optional)", placeholder="defaults to the symbol").strip().upper()
    submitted = st.form_submit_button("Search & Add")

if submitted and new_symbol:
    sector_name = new_name or new_symbol
    with st.spinner(f"Looking up {new_exchange}:{new_symbol} on TradingView..."):
        try:
            probe = fetch_tv.fetch_ohlc(new_symbol, new_exchange, "1D")
            last_close = probe["close"].iloc[-1]
        except Exception as exc:
            st.sidebar.error(f"Couldn't fetch {new_exchange}:{new_symbol} — {exc}")
            probe = None

    if probe is not None:
        sectors_store.add_sector(sector_name, new_symbol, new_exchange)
        conn = db.get_connection()
        with st.spinner(f"Ingesting Daily/Weekly/Monthly history for {sector_name}..."):
            for tf in config.TIMEFRAMES:
                ingest_one(conn, sector_name, new_symbol, new_exchange, tf)
        conn.close()
        st.sidebar.success(f"Added {sector_name} ({new_exchange}:{new_symbol}), last close {last_close:.2f}")
        st.cache_data.clear()
        st.rerun()

if active_sectors:
    st.sidebar.caption(f"Tracking {len(active_sectors)} sector(s):")
    for name, (sym, exch) in sorted(active_sectors.items()):
        cols = st.sidebar.columns([4, 1])
        cols[0].write(f"**{name}** ({exch}:{sym})")
        if cols[1].button("✕", key=f"remove_{name}", help=f"Stop tracking {name}"):
            sectors_store.remove_sector(name)
            st.cache_data.clear()
            st.rerun()

st.sidebar.divider()

df = load_data()
df = df[df["sector"].isin(active_sectors.keys())]

if df.empty:
    st.warning("No data yet. Add a sector above, or run `python src/ingest.py` first.")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar: user-configurable, dynamic number of classification bands
# ---------------------------------------------------------------------------
st.sidebar.header("Classification bands")
st.sidebar.caption("A value belongs to the highest band whose minimum it clears.")

bands = bands_store.load_bands()  # sorted ascending by min

for band in sorted(bands, key=lambda b: -b["min"]):
    cols = st.sidebar.columns([1, 4, 1])
    cols[0].markdown(
        f'<div style="width:22px; height:22px; border-radius:4px; background:{band["color"]}; margin-top:6px;"></div>',
        unsafe_allow_html=True,
    )
    cols[1].write(f"**{band['name']}** (RSI ≥ {band['min']:.0f})")
    if cols[2].button("✕", key=f"remove_band_{band['name']}", help=f"Remove {band['name']}"):
        remaining = [b for b in bands if b["name"] != band["name"]]
        if remaining:
            bands_store.save_bands(remaining)
            st.rerun()
        else:
            st.sidebar.error("You need at least one band.")

st.sidebar.caption("Add a band")
add_cols = st.sidebar.columns([3, 2, 2])
new_band_name = add_cols[0].text_input("Name", key="new_band_name", label_visibility="collapsed", placeholder="Name")
new_band_min = add_cols[1].number_input("Min", key="new_band_min", value=50.0, step=1.0, label_visibility="collapsed")
new_band_color = add_cols[2].color_picker("Color", key="new_band_color", value="#3288bd", label_visibility="collapsed")
if st.sidebar.button("Add band", key="add_band_btn"):
    if new_band_name.strip():
        bands_store.add_band(new_band_name.strip(), new_band_min, new_band_color)
        st.rerun()
    else:
        st.sidebar.error("Give the new band a name.")

st.sidebar.divider()

# ---------------------------------------------------------------------------
# Sidebar: ADX highlight (independent of RSI band colors)
# ---------------------------------------------------------------------------
st.sidebar.header("ADX highlight")
st.sidebar.caption("Flags a strong trend (high ADX) with its own color, separate from the RSI bands.")

adx_cfg = adx_store.load_config()
adx_cols = st.sidebar.columns([2, 1])
adx_threshold_input = adx_cols[0].number_input(
    "ADX >", min_value=0.0, max_value=100.0, value=float(adx_cfg["threshold"]), step=1.0, label_visibility="collapsed"
)
adx_color_input = adx_cols[1].color_picker("Color", value=adx_cfg["color"], label_visibility="collapsed")
if st.sidebar.button("Save ADX setting", key="save_adx_btn"):
    adx_store.save_config(adx_threshold_input, adx_color_input)
    st.rerun()

ADX_THRESHOLD = adx_cfg["threshold"]
ADX_COLOR = adx_cfg["color"]

st.sidebar.divider()

BAND_ORDER = [b["name"] for b in sorted(bands, key=lambda b: -b["min"])]
BAND_COLORS = {b["name"]: b["color"] for b in bands}


def _band_label(band, bands_sorted):
    idx = bands_sorted.index(band)
    if idx == len(bands_sorted) - 1:
        return f"{band['name']} — RSI ≥ {band['min']:.0f}"
    return f"{band['name']} — RSI {band['min']:.0f}-{bands_sorted[idx + 1]['min']:.0f}"


BAND_LABELS = {b["name"]: _band_label(b, bands) for b in bands}


def classify(rsi):
    if pd.isna(rsi):
        return None
    return bands_store.classify(rsi, bands)


# ---------------------------------------------------------------------------
# Latest reading per sector x timeframe, reclassified live using the sidebar settings
# ---------------------------------------------------------------------------
all_latest = df.sort_values("date").groupby(["sector", "timeframe"], as_index=False).last()
all_latest["classification"] = all_latest["rsi"].apply(classify)

sectors = sorted(all_latest["sector"].unique())
cell_lookup = {(r["sector"], r["timeframe"]): r for _, r in all_latest.iterrows()}

st.title("Sector Strength Dashboard")

as_of_by_tf = {
    tf: all_latest.loc[all_latest["timeframe"] == tf, "date"].max()
    for tf in tf_order
    if (all_latest["timeframe"] == tf).any()
}
st.caption("As of — " + " | ".join(f"{tf_names[tf]}: {d.date()}" for tf, d in as_of_by_tf.items()))

# ---------------------------------------------------------------------------
# Monthly-Weekly-Daily pattern filter
# ---------------------------------------------------------------------------
st.subheader("Filter by Monthly-Weekly-Daily pattern")

PRESETS = {f"All {name}": (name, name, name) for name in BAND_ORDER}

preset_choice = st.selectbox("Quick pattern", [ANY] + list(PRESETS.keys()))
preset_bands = PRESETS.get(preset_choice, (ANY, ANY, ANY))

filter_cols = st.columns(3)
band_options = [ANY] + BAND_ORDER
monthly_filter = filter_cols[0].selectbox("Monthly (M)", band_options, index=band_options.index(preset_bands[0]))
weekly_filter = filter_cols[1].selectbox("Weekly (W)", band_options, index=band_options.index(preset_bands[1]))
daily_filter = filter_cols[2].selectbox("Daily (D)", band_options, index=band_options.index(preset_bands[2]))

active_filter = {"1M": monthly_filter, "1W": weekly_filter, "1D": daily_filter}
filter_is_active = any(v != ANY for v in active_filter.values())


def sector_matches_filter(sector):
    for tf, wanted in active_filter.items():
        if wanted == ANY:
            continue
        r = cell_lookup.get((sector, tf))
        if r is None or r["classification"] != wanted:
            return False
    return True


matching_sectors = [s for s in sectors if sector_matches_filter(s)]

if filter_is_active:
    st.caption(
        f"Pattern M-W-D = {active_filter['1M']}-{active_filter['1W']}-{active_filter['1D']} "
        f"→ {len(matching_sectors)} sector(s) match"
    )

def adx_html(adx_value):
    if adx_value > ADX_THRESHOLD:
        return f'<b style="color:{ADX_COLOR};">ADX {adx_value:.2f} ▲</b>'
    return f'ADX {adx_value:.2f}'


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------
st.subheader("All Timeframes — One Board")
legend_items = "".join(
    f'<span style="border-left:6px solid {BAND_COLORS[b]}; padding-left:6px; white-space:nowrap;">{BAND_LABELS[b]}</span>'
    for b in BAND_ORDER
)
legend_items += (
    f'<span style="border-left:6px solid {ADX_COLOR}; padding-left:6px; white-space:nowrap;">'
    f'Strong trend — ADX &gt; {ADX_THRESHOLD:.0f}</span>'
)
st.markdown(
    f'<div style="display:flex; flex-wrap:wrap; gap:12px; margin-bottom:8px;">{legend_items}</div>',
    unsafe_allow_html=True,
)

rows_to_show = matching_sectors if filter_is_active else sectors

if not rows_to_show:
    st.info("No sectors match this pattern.")
else:
    header_cells = "".join(f'<th style="text-align:left;">{tf_names[tf]} ({tf})</th>' for tf in tf_order)
    table_html = f"""
    <div class="table-scroll"><table style="width:100%;">
    <thead>
    <tr style="border-bottom:2px solid #444;">
    <th style="text-align:left;">Sector</th>
    {header_cells}
    </tr>
    </thead>
    <tbody>
    """

    for sector in rows_to_show:
        table_html += f'<tr style="border-bottom:1px solid #333;"><td style="font-weight:700;">{sector}</td>'
        for tf in tf_order:
            r = cell_lookup.get((sector, tf))
            if r is None:
                table_html += '<td>—</td>'
                continue
            color = BAND_COLORS.get(r["classification"], "#888")
            table_html += (
                f'<td style="background:{color}2b; border-left:4px solid {color}; white-space:normal;">'
                f'RSI {r["rsi"]:.2f} &nbsp; RSI-MA {r["rsi_ma"]:.2f} &nbsp; {adx_html(r["adx"])}'
                f'<br/><span style="opacity:0.75;">{r["classification"]}</span>'
                f'</td>'
            )
        table_html += "</tr>"

    table_html += "</tbody></table></div>"
    st.markdown(table_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Day-to-Day comparison (Daily timeframe, user-selected dates)
# ---------------------------------------------------------------------------
st.subheader("Day-to-Day Comparison (Daily)")

daily_df = df[df["timeframe"] == "1D"].copy()
daily_df["classification"] = daily_df["rsi"].apply(classify)
available_dates = sorted(daily_df["date"].dt.date.unique(), reverse=True)
min_date, max_date = min(available_dates), max(available_dates)

pick_mode = st.radio("Pick", ["Specific dates", "Date range"], horizontal=True, key="day_pick_mode")

if pick_mode == "Date range":
    range_value = st.date_input(
        "Range",
        value=(max(min_date, available_dates[min(4, len(available_dates) - 1)]), max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(range_value, tuple) and len(range_value) == 2:
        range_start, range_end = range_value
        selected_dates = [d for d in available_dates if range_start <= d <= range_end]
    else:
        selected_dates = []
        st.info("Pick both a start and end date.")
else:
    default_dates = available_dates[: min(5, len(available_dates))]
    selected_dates = st.multiselect(
        "Dates to compare",
        options=available_dates,
        default=default_dates,
        format_func=lambda d: d.isoformat(),
    )

if not selected_dates:
    st.info("Select at least one date to compare.")
else:
    selected_dates_sorted = sorted(selected_dates)
    day_cell_lookup = {
        (r["sector"], r["date"].date()): r
        for _, r in daily_df[daily_df["date"].dt.date.isin(selected_dates_sorted)].iterrows()
    }

    header_cells = "".join(
        f'<th style="text-align:left;">{d.isoformat()}</th>' for d in selected_dates_sorted
    )
    day_table_html = f"""
    <div class="table-scroll"><table style="width:100%;">
    <thead>
    <tr style="border-bottom:2px solid #444;">
    <th style="text-align:left;">Sector</th>
    {header_cells}
    </tr>
    </thead>
    <tbody>
    """

    for sector in sectors:
        day_table_html += f'<tr style="border-bottom:1px solid #333;"><td style="font-weight:700;">{sector}</td>'
        for d in selected_dates_sorted:
            r = day_cell_lookup.get((sector, d))
            if r is None:
                day_table_html += '<td>—</td>'
                continue
            color = BAND_COLORS.get(r["classification"], "#888")
            day_table_html += (
                f'<td style="background:{color}2b; border-left:4px solid {color}; white-space:normal;">'
                f'RSI {r["rsi"]:.2f} &nbsp; ADX {r["adx"]:.2f}'
                f'<br/><span style="opacity:0.75;">{r["classification"]}</span>'
                f'</td>'
            )
        day_table_html += "</tr>"

    day_table_html += "</tbody></table></div>"
    st.markdown(day_table_html, unsafe_allow_html=True)

with st.expander("Raw data"):
    raw = all_latest[["timeframe", "sector", "close", "rsi", "rsi_ma", "adx", "classification", "date"]].sort_values(
        ["timeframe", "rsi"], ascending=[True, False]
    )
    st.dataframe(
        raw.style.format({"close": "{:.2f}", "rsi": "{:.2f}", "rsi_ma": "{:.2f}", "adx": "{:.2f}"}),
        use_container_width=True,
    )
