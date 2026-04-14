"""
初始持倉設定
直接填「我現在持有 X 股 @ Y 元」，不需要填完整交易紀錄
適合第一次設定、或匯入現有持倉
"""

import streamlit as st
from datetime import date

from utils.notion_loader import add_trade

st.set_page_config(page_title="初始持倉", page_icon="🔧", layout="wide")

st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
</style>
""", unsafe_allow_html=True)

st.title("🔧 初始持倉設定")
st.caption("已持有部位快速匯入，只需填股票、股數、成本均價。不需要原始交易紀錄。")

COMMON_TICKERS = [
    "2330.TW", "2308.TW", "2383.TW", "3715.TW",
    "NVDA", "AAPL", "MSFT", "TSLA",
]
TERM_OPTIONS = {"長期 (long)": "long", "中期 (mid)": "mid", "短期 (short)": "short"}

st.info("每筆代表一個持倉部位。成本均價已含手續費時，手續費欄位填 0 即可。")

col1, col2 = st.columns(2)

with col1:
    ticker_mode = st.radio("股票代號", ["從清單選擇", "手動輸入"], horizontal=True, key="ip_mode")
    if ticker_mode == "從清單選擇":
        ticker = st.selectbox("股票", COMMON_TICKERS, key="ip_ticker_select")
    else:
        ticker = st.text_input("股票代號（例：2330.TW）", key="ip_ticker_manual").strip().upper()

    term_label = st.selectbox("投資期別", list(TERM_OPTIONS.keys()), key="ip_term")

with col2:
    shares = st.number_input("目前持有股數", min_value=0.0, step=1.0, format="%.0f", key="ip_shares")
    avg_cost = st.number_input(
        "成本均價（元）",
        min_value=0.0, step=0.01, format="%.2f", key="ip_avg_cost",
        help="買入均價，已含手續費則手續費填 0",
    )
    buy_date = st.date_input(
        "買入日期（可填大概日期）",
        value=date.today(),
        max_value=date.today(),
        key="ip_date",
    )

note = st.text_area("備註（選填，例：分批買入均價）", height=68, key="ip_note")

if st.button("✅ 匯入持倉", type="primary", use_container_width=True):
    term = TERM_OPTIONS[term_label]
    errors = []
    if not ticker:
        errors.append("請填寫股票代號")
    if shares <= 0:
        errors.append("股數需大於 0")
    if avg_cost <= 0:
        errors.append("成本均價需大於 0")

    if errors:
        for err in errors:
            st.error(err)
    else:
        try:
            add_trade(
                ticker=ticker,
                action="buy",
                term=term,
                trade_date=buy_date,
                shares=shares,
                price=avg_cost,
                fee=0.0,
                reason="初始持倉匯入",
                note=note.strip(),
            )
            term_chinese = {"long": "長期", "mid": "中期", "short": "短期"}[term]
            st.success(
                f"✅ 已匯入：{ticker} {shares:,.0f} 股 @ ${avg_cost:,.2f}（{term_chinese}）"
            )
            for key in ["ip_ticker_select", "ip_ticker_manual", "ip_term",
                        "ip_shares", "ip_avg_cost", "ip_note"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.cache_data.clear()
        except Exception as e:
            st.error(f"寫入 Notion 失敗：{e}")
