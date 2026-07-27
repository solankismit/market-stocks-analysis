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
import config  # noqa: E402
import db  # noqa: E402
import fetch_tv  # noqa: E402
import sectors_store  # noqa: E402
from ingest import ingest_one  # noqa: E402

st.set_page_config(page_title="Sector Strength Dashboard", layout="wide")

STRONG, NEUTRAL, WEAK = config.STRONG, config.NEUTRAL, config.WEAK
BAND_ORDER = [STRONG, NEUTRAL, WEAK]
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
# Sidebar: user-configurable thresholds + colors
# ---------------------------------------------------------------------------
st.sidebar.header("Classification settings")

strong_threshold = st.sidebar.number_input(
    "Strong threshold (RSI >)", min_value=0.0, max_value=100.0, value=config.STRONG_THRESHOLD, step=1.0
)
weak_threshold = st.sidebar.number_input(
    "Weak threshold (RSI <)", min_value=0.0, max_value=100.0, value=config.WEAK_THRESHOLD, step=1.0
)
if weak_threshold >= strong_threshold:
    st.sidebar.error("Weak threshold must be lower than the Strong threshold.")
    st.stop()

st.sidebar.subheader("Band colors")
strong_color = st.sidebar.color_picker("Strong color", "#1a9850")
neutral_color = st.sidebar.color_picker("Neutral color", "#e6b800")
weak_color = st.sidebar.color_picker("Weak color", "#d73027")

BAND_COLORS = {STRONG: strong_color, NEUTRAL: neutral_color, WEAK: weak_color}
BAND_LABELS = {
    STRONG: f"Strong — RSI > {strong_threshold:.0f}",
    NEUTRAL: f"Neutral — RSI {weak_threshold:.0f}-{strong_threshold:.0f}",
    WEAK: f"Weak — RSI < {weak_threshold:.0f}",
}


def classify(rsi):
    if pd.isna(rsi):
        return None
    if rsi > strong_threshold:
        return STRONG
    if rsi < weak_threshold:
        return WEAK
    return NEUTRAL


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

PRESETS = {
    "All Strong (60-60-60)": (STRONG, STRONG, STRONG),
    "M+W Strong, D Weak (60-60-40)": (STRONG, STRONG, WEAK),
    "M Strong, W+D Weak (60-40-40)": (STRONG, WEAK, WEAK),
    "M+W Weak, D Strong (40-40-60)": (WEAK, WEAK, STRONG),
    "All Weak (40-40-40)": (WEAK, WEAK, WEAK),
}

preset_choice = st.selectbox("Quick pattern", [ANY] + list(PRESETS.keys()))
preset_bands = PRESETS.get(preset_choice, (ANY, ANY, ANY))

filter_cols = st.columns(3)
band_options = [ANY, STRONG, NEUTRAL, WEAK]
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

# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------
st.subheader("All Timeframes — One Board")
legend = " &nbsp;&nbsp; ".join(
    f'<span style="border-left:6px solid {BAND_COLORS[b]}; padding-left:6px;">{BAND_LABELS[b]}</span>'
    for b in BAND_ORDER
)
st.markdown(legend, unsafe_allow_html=True)
st.write("")

rows_to_show = matching_sectors if filter_is_active else sectors

if not rows_to_show:
    st.info("No sectors match this pattern.")
else:
    header_cells = "".join(f'<th style="padding:8px 14px; text-align:left;">{tf_names[tf]} ({tf})</th>' for tf in tf_order)
    table_html = f"""
    <table style="width:100%; border-collapse:collapse;">
    <thead>
    <tr style="border-bottom:2px solid #444;">
    <th style="padding:8px 14px; text-align:left;">Sector</th>
    {header_cells}
    </tr>
    </thead>
    <tbody>
    """

    for sector in rows_to_show:
        table_html += f'<tr style="border-bottom:1px solid #333;"><td style="padding:8px 14px; font-weight:700;">{sector}</td>'
        for tf in tf_order:
            r = cell_lookup.get((sector, tf))
            if r is None:
                table_html += '<td style="padding:8px 14px;">—</td>'
                continue
            color = BAND_COLORS.get(r["classification"], "#888")
            table_html += (
                f'<td style="padding:8px 14px; background:{color}2b; border-left:4px solid {color};">'
                f'RSI {r["rsi"]:.2f} &nbsp; RSI-MA {r["rsi_ma"]:.2f} &nbsp; ADX {r["adx"]:.2f}'
                f'<br/><span style="opacity:0.75;">{r["classification"]}</span>'
                f'</td>'
            )
        table_html += "</tr>"

    table_html += "</tbody></table>"
    st.markdown(table_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Day-to-Day comparison (Daily timeframe, user-selected dates)
# ---------------------------------------------------------------------------
st.subheader("Day-to-Day Comparison (Daily)")

daily_df = df[df["timeframe"] == "1D"].copy()
daily_df["classification"] = daily_df["rsi"].apply(classify)
available_dates = sorted(daily_df["date"].dt.date.unique(), reverse=True)

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
        f'<th style="padding:8px 14px; text-align:left;">{d.isoformat()}</th>' for d in selected_dates_sorted
    )
    day_table_html = f"""
    <table style="width:100%; border-collapse:collapse;">
    <thead>
    <tr style="border-bottom:2px solid #444;">
    <th style="padding:8px 14px; text-align:left;">Sector</th>
    {header_cells}
    </tr>
    </thead>
    <tbody>
    """

    for sector in sectors:
        day_table_html += f'<tr style="border-bottom:1px solid #333;"><td style="padding:8px 14px; font-weight:700;">{sector}</td>'
        for d in selected_dates_sorted:
            r = day_cell_lookup.get((sector, d))
            if r is None:
                day_table_html += '<td style="padding:8px 14px;">—</td>'
                continue
            color = BAND_COLORS.get(r["classification"], "#888")
            day_table_html += (
                f'<td style="padding:8px 14px; background:{color}2b; border-left:4px solid {color};">'
                f'RSI {r["rsi"]:.2f} &nbsp; ADX {r["adx"]:.2f}'
                f'<br/><span style="opacity:0.75;">{r["classification"]}</span>'
                f'</td>'
            )
        day_table_html += "</tr>"

    day_table_html += "</tbody></table>"
    st.markdown(day_table_html, unsafe_allow_html=True)

with st.expander("Raw data"):
    raw = all_latest[["timeframe", "sector", "close", "rsi", "rsi_ma", "adx", "classification", "date"]].sort_values(
        ["timeframe", "rsi"], ascending=[True, False]
    )
    st.dataframe(
        raw.style.format({"close": "{:.2f}", "rsi": "{:.2f}", "rsi_ma": "{:.2f}", "adx": "{:.2f}"}),
        use_container_width=True,
    )
