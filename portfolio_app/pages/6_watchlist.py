"""
觀察清單
追蹤感興趣的股票即時報價與漲跌
清單存放於 Notion（與交易紀錄同一 DB，action="watch"），每位用戶獨立管理。
"""

import streamlit as st
import yfinance as yf
from utils.ticker_names import get_name
from utils.auth import require_login
from utils.notion_loader import fetch_watchlist, add_to_watchlist, delete_trade

st.set_page_config(page_title="觀察清單", page_icon="👁️", layout="wide")

st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
</style>
""", unsafe_allow_html=True)

current_user = require_login()

st.title("👁️ 觀察清單")
st.caption("快速查看感興趣的股票現況。清單永久保存於 Notion，重新整理也不會消失。")

# ── 從 Notion 讀取觀察清單 ───────────────────────────────────────────────────
@st.cache_data(ttl=60)
def _load_watchlist(user: str) -> list[dict]:
    return fetch_watchlist(user)

watchlist_items = _load_watchlist(current_user)
watchlist_tickers = [item["ticker"] for item in watchlist_items if item["ticker"]]

# ── 新增股票 ──────────────────────────────────────────────────────────────────
col_add, col_btn = st.columns([3, 1])
with col_add:
    new_ticker = st.text_input(
        "新增股票代號",
        placeholder="例：2454.TW 或 AAPL",
        label_visibility="collapsed",
    ).strip().upper()
with col_btn:
    if st.button("新增", use_container_width=True):
        if not new_ticker:
            st.warning("請輸入股票代號")
        elif new_ticker in watchlist_tickers:
            st.warning(f"{new_ticker} 已在清單中")
        else:
            with st.spinner("新增中..."):
                try:
                    add_to_watchlist(new_ticker, current_user)
                    st.cache_data.clear()
                    st.success(f"已新增 {new_ticker}")
                    st.rerun()
                except Exception as e:
                    st.error(f"新增失敗：{e}")

if not watchlist_tickers:
    st.info("觀察清單為空，請輸入股票代號新增。")
    st.stop()

# ── 讀取報價 ──────────────────────────────────────────────────────────────────
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

col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("🔄 重新整理"):
        st.cache_data.clear()
        st.rerun()

with st.spinner("載入報價..."):
    data = fetch_watchlist_data(tuple(watchlist_tickers))

# 建立 ticker -> page_id 對應（供刪除用）
ticker_to_page = {item["ticker"]: item["page_id"] for item in watchlist_items}

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
                    f"""<div style="background:#1C1C2E;border-radius:12px;padding:14px 16px;margin-bottom:4px;">
  <div style="font-weight:700;">{d['name']}</div>
  <div style="color:#888;font-size:0.85em;">{d['ticker']}</div>
  <div style="color:#666;margin-top:6px;">無法取得報價</div>
</div>""",
                    unsafe_allow_html=True,
                )
            else:
                chg = d["change"]
                chg_pct = d["change_pct"]
                color = COLOR_UP if chg > 0 else (COLOR_DOWN if chg < 0 else COLOR_NEUTRAL)
                arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")
                sign = "+" if chg >= 0 else ""
                name_display = d["name"] if d["name"] != d["ticker"] else ""

                st.markdown(
                    f"""<div style="background:#1C1C2E;border-radius:12px;padding:14px 16px;margin-bottom:4px;">
  <div style="font-size:1.05em;font-weight:700;">{name_display or d['ticker']}</div>
  <div style="color:#888;font-size:0.82em;margin-bottom:6px;">{d['ticker']}</div>
  <div style="font-size:1.5em;font-weight:700;">${d['price']:,.2f}</div>
  <div style="font-size:1em;color:{color};margin-top:2px;">
    {arrow} {sign}{chg:,.2f}　({sign}{chg_pct:.2f}%)
  </div>
</div>""",
                    unsafe_allow_html=True,
                )

            # 刪除按鈕
            page_id = ticker_to_page.get(d["ticker"])
            if page_id and st.button(
                f"移除 {d['ticker']}", key=f"rm_{d['ticker']}",
                use_container_width=True,
            ):
                with st.spinner(f"移除 {d['ticker']}..."):
                    try:
                        delete_trade(page_id)
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"移除失敗：{e}")
