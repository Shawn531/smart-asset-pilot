"""
新增交易 / 現金入出金
驗證失敗時保留所有已填欄位，不重置
"""

import streamlit as st
from datetime import date

from utils.notion_loader import add_trade
from utils.auth import require_login

st.set_page_config(page_title="新增交易", page_icon="➕", layout="wide")
current_user = require_login()

st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
</style>
""", unsafe_allow_html=True)

st.title("➕ 新增紀錄")

COMMON_TICKERS = [
    "2330.TW", "2308.TW", "2383.TW", "3715.TW",
    "NVDA", "AAPL", "MSFT", "TSLA",
]
TERM_OPTIONS = {"長期 (long)": "long", "中期 (mid)": "mid", "短期 (short)": "short"}

# ── 切換：股票交易 / 現金 ─────────────────────────────────────────────────────
record_type = st.radio(
    "紀錄類型",
    ["📈 股票交易", "💵 現金入出金"],
    horizontal=True,
    key="record_type",
)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
if record_type == "📈 股票交易":

    col1, col2 = st.columns(2)

    with col1:
        ticker_mode = st.radio(
            "股票代號輸入方式",
            ["從清單選擇", "手動輸入"],
            horizontal=True,
            key="ticker_mode",
        )
        if ticker_mode == "從清單選擇":
            ticker = st.selectbox("股票代號", COMMON_TICKERS, key="ticker_select")
        else:
            ticker = st.text_input(
                "股票代號（例：2330.TW）", key="ticker_manual"
            ).strip().upper()

        action_label = st.selectbox(
            "操作", ["買入 (buy)", "賣出 (sell)"], key="stock_action"
        )
        term_label = st.selectbox("投資期別", list(TERM_OPTIONS.keys()), key="term")

    with col2:
        trade_date = st.date_input(
            "交易日期", value=date.today(), max_value=date.today(), key="trade_date"
        )
        shares = st.number_input("股數", min_value=0.0, step=1.0, format="%.0f", key="shares")
        price = st.number_input("成交均價（元）", min_value=0.0, step=0.01, format="%.2f", key="price")

        # 自動計算手續費（台灣標準：0.1425% × 折扣，最低 $20；賣出加證交稅 0.3%）
        _action_type = "sell" if "sell" in action_label else "buy"
        _discount = float(st.secrets.get("FEE_DISCOUNT", 0.6))
        if shares > 0 and price > 0:
            _amount = shares * price
            _brokerage = max(20.0, round(_amount * 0.001425 * _discount))
            if _action_type == "sell":
                _tx_tax = round(_amount * 0.003)
                _computed_fee = _brokerage + _tx_tax
                _fee_hint = f"建議：手續費 ${_brokerage:,.0f} ＋ 證交稅 ${_tx_tax:,.0f} ＝ ${_computed_fee:,.0f}"
            else:
                _computed_fee = _brokerage
                _fee_hint = f"建議：${_computed_fee:,.0f}（0.1425% × {_discount:.0%}，最低 $20）"
        else:
            _computed_fee = 0.0
            _fee_hint = ""

        fee = st.number_input(
            "手續費（含券商費＋證交稅，自動估算可覆寫）",
            min_value=0.0,
            value=float(_computed_fee),
            step=1.0, format="%.0f",
            key="fee",
        )
        if _fee_hint:
            st.caption(_fee_hint)

    reason = st.text_area(
        "買入/賣出理由 *（必填）",
        placeholder="例：AI 週期回升，逢低佈局...",
        height=100,
        key="reason",
    )
    note = st.text_area("備註（選填）", height=68, key="note")

    if st.button("✅ 確認送出", type="primary", use_container_width=True):
        action = "buy" if "buy" in action_label else "sell"
        term = TERM_OPTIONS[term_label]
        errors = []
        if not ticker:
            errors.append("請填寫股票代號")
        if shares <= 0:
            errors.append("股數需大於 0")
        if price <= 0:
            errors.append("成交均價需大於 0")
        if not reason.strip():
            errors.append("請填寫買入/賣出理由")

        if errors:
            for err in errors:
                st.error(err)
        else:
            try:
                add_trade(
                    ticker=ticker,
                    action=action,
                    term=term,
                    trade_date=trade_date,
                    shares=shares,
                    price=price,
                    fee=fee,
                    reason=reason.strip(),
                    note=note.strip(),
                    user=current_user,
                )
                action_zh = "買入" if action == "buy" else "賣出"
                term_zh = {"long": "長期", "mid": "中期", "short": "短期"}[term]
                st.success(f"✅ 已記錄：{action_zh} {ticker} {shares:,.0f} 股 @ ${price:,.2f}（{term_zh}）")
                for key in ["ticker_select", "ticker_manual", "stock_action", "term",
                            "shares", "price", "fee", "reason", "note"]:
                    st.session_state.pop(key, None)
                st.cache_data.clear()
            except Exception as e:
                st.error(f"寫入 Notion 失敗：{e}")

# ══════════════════════════════════════════════════════════════════════════════
else:
    st.caption("入金 / 出金紀錄會影響現金餘額計算，請確實記錄每次資金異動。")

    col1, col2 = st.columns(2)
    with col1:
        cash_action = st.selectbox(
            "類型",
            ["入金（存入資金）", "出金（提出資金）"],
            key="cash_action",
        )
        cash_date = st.date_input(
            "日期", value=date.today(), max_value=date.today(), key="cash_date"
        )
    with col2:
        cash_amount = st.number_input(
            "金額（NTD）", min_value=0.0, step=1000.0, format="%.0f", key="cash_amount"
        )

    cash_reason = st.text_area(
        "說明（選填）",
        placeholder="例：薪資轉入、獲利出金...",
        height=80,
        key="cash_reason",
    )

    if st.button("✅ 確認送出", type="primary", use_container_width=True):
        action = "deposit" if "入金" in cash_action else "withdraw"
        if cash_amount <= 0:
            st.error("金額需大於 0")
        else:
            try:
                add_trade(
                    ticker="CASH",
                    action=action,
                    term="long",
                    trade_date=cash_date,
                    shares=1,
                    price=cash_amount,
                    fee=0.0,
                    reason=cash_reason.strip() or ("入金" if action == "deposit" else "出金"),
                    user=current_user,
                )
                action_zh = "入金" if action == "deposit" else "出金"
                st.success(f"✅ 已記錄：{action_zh} ${cash_amount:,.0f}")
                for key in ["cash_action", "cash_amount", "cash_reason"]:
                    st.session_state.pop(key, None)
                st.cache_data.clear()
            except Exception as e:
                st.error(f"寫入 Notion 失敗：{e}")
