"""
觀察清單
追蹤感興趣的股票即時報價與漲跌
在 .streamlit/secrets.toml 中設定 WATCHLIST 清單
"""

import streamlit as st
import yfinance as yf
from utils.ticker_names import get_name, TICKER_TO_NAME

st.set_page_config(page_title="觀察清單", page_icon="👁️", layout="wide")

st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
</style>
""", unsafe_allow_html=True)

st.title("👁️ 觀察清單")
st.caption("快速查看感興趣的股票現況。")

# ── 從 secrets 讀取清單 ───────────────────────────────────────────────────────
default_watchlist = ["2330.TW", "2308.TW", "0050.TW", "00878.TW", "NVDA"]
try:
    watchlist = list(st.secrets.get("WATCHLIST", default_watchlist))
except Exception:
    watchlist = default_watchlist

# ── 手動新增股票（session 內有效）────────────────────────────────────────────
if "watchlist_extra" not in st.session_state:
    st.session_state.watchlist_extra = []

col_add, col_btn = st.columns([3, 1])
with col_add:
    new_ticker = st.text_input(
        "新增股票代號（本次有效）",
        placeholder="例：2454.TW 或 AAPL",
        label_visibility="collapsed",
    ).strip().upper()
with col_btn:
    if st.button("新增", use_container_width=True):
        if new_ticker and new_ticker not in watchlist and new_ticker not in st.session_state.watchlist_extra:
            st.session_state.watchlist_extra.append(new_ticker)

all_tickers = watchlist + st.session_state.watchlist_extra

if not all_tickers:
    st.info("觀察清單為空。請在 .streamlit/secrets.toml 中設定 WATCHLIST，或在上方手動新增。")
    st.stop()

# ── 讀取價格 ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=120)
def fetch_watchlist_data(tickers: tuple) -> list[dict]:
    results = []
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).fast_info
            price = info.last_price
            prev = info.previous_close
            if price is None or prev is None:
                raise ValueError("no price")
            change = price - prev
            change_pct = change / prev * 100
            results.append({
                "ticker": ticker,
                "name": get_name(ticker),
                "price": round(float(price), 2),
                "change": round(float(change), 2),
                "change_pct": round(float(change_pct), 2),
                "ok": True,
            })
        except Exception:
            results.append({"ticker": ticker, "name": get_name(ticker), "ok": False})
    return results

with st.spinner("載入報價..."):
    data = fetch_watchlist_data(tuple(all_tickers))

if st.button("🔄 重新整理"):
    st.cache_data.clear()
    st.rerun()

st.divider()

# ── 顯示卡片 ──────────────────────────────────────────────────────────────────
COLOR_UP = "#E05C5C"
COLOR_DOWN = "#4CAF82"
COLOR_NEUTRAL = "#AAAAAA"

cols_per_row = 3
for i in range(0, len(data), cols_per_row):
    cols = st.columns(cols_per_row)
    for j, d in enumerate(data[i: i + cols_per_row]):
        with cols[j]:
            if not d["ok"]:
                st.markdown(
                    f"""<div style="background:#1C1C2E;border-radius:12px;padding:14px 16px;margin-bottom:10px;">
  <div style="font-weight:700;">{d['name']}</div>
  <div style="color:#888;font-size:0.85em;">{d['ticker']}</div>
  <div style="color:#666;margin-top:6px;">無法取得報價</div>
</div>""",
                    unsafe_allow_html=True,
                )
                continue

            chg = d["change"]
            chg_pct = d["change_pct"]
            color = COLOR_UP if chg > 0 else (COLOR_DOWN if chg < 0 else COLOR_NEUTRAL)
            arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")
            sign = "+" if chg >= 0 else ""
            name_display = d["name"] if d["name"] != d["ticker"] else ""

            st.markdown(
                f"""<div style="background:#1C1C2E;border-radius:12px;padding:14px 16px;margin-bottom:10px;">
  <div style="font-size:1.05em;font-weight:700;">{name_display or d['ticker']}</div>
  <div style="color:#888;font-size:0.82em;margin-bottom:6px;">{d['ticker']}</div>
  <div style="font-size:1.5em;font-weight:700;">${d['price']:,.2f}</div>
  <div style="font-size:1em;color:{color};margin-top:2px;">
    {arrow} {sign}{chg:,.2f}　({sign}{chg_pct:.2f}%)
  </div>
</div>""",
                unsafe_allow_html=True,
            )

st.caption("報價每 2 分鐘自動快取。如需要常駐觀察清單，請在 .streamlit/secrets.toml 新增：`WATCHLIST = [\"2330.TW\", \"0050.TW\"]`")
