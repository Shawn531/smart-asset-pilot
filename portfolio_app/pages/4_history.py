"""
交易紀錄
歷史交易清單，支援篩選、刪除、匯出 CSV
"""

import streamlit as st
import pandas as pd

from utils.notion_loader import fetch_trades, delete_trade

st.set_page_config(page_title="交易紀錄", page_icon="📋", layout="wide")

st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
</style>
""", unsafe_allow_html=True)

st.title("📋 交易紀錄")

TERM_LABELS = {"long": "長期", "mid": "中期", "short": "短期"}
ACTION_LABELS = {
    "buy": "買入", "sell": "賣出",
    "deposit": "入金", "withdraw": "出金",
}
ACTION_COLORS = {
    "buy": "#E05C5C", "sell": "#4CAF82",
    "deposit": "#FFD700", "withdraw": "#AAAAAA",
}

@st.cache_data(ttl=300)
def load_trades():
    return fetch_trades()

with st.spinner("載入交易紀錄..."):
    try:
        trades = load_trades()
    except Exception as e:
        st.error(f"無法載入資料：{e}")
        st.stop()

if not trades:
    st.info("尚無交易紀錄，請先至「新增交易」頁面新增。")
    st.stop()

# ── 篩選器 ────────────────────────────────────────────────────────────────────
all_tickers = sorted(set(t["ticker"] for t in trades if t["ticker"] and t["ticker"] != "CASH"))
all_actions = sorted(set(t["action"] for t in trades if t["action"]))

fc1, fc2, fc3 = st.columns([2, 2, 1])
with fc1:
    selected_tickers = st.multiselect(
        "篩選股票", ["CASH"] + all_tickers, default=[]
    )
with fc2:
    selected_actions = st.multiselect(
        "篩選類型",
        options=list(ACTION_LABELS.keys()),
        format_func=lambda x: ACTION_LABELS.get(x, x),
        default=[],
    )
with fc3:
    sort_order = st.selectbox("排序", ["最新在前", "最舊在前"])

filtered = trades
if selected_tickers:
    filtered = [t for t in filtered if t["ticker"] in selected_tickers]
if selected_actions:
    filtered = [t for t in filtered if t["action"] in selected_actions]
filtered = sorted(filtered, key=lambda x: x["date"] or "", reverse=(sort_order == "最新在前"))

st.caption(f"共 {len(filtered)} 筆紀錄")

# ── 刪除確認 state ────────────────────────────────────────────────────────────
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = None

# ── 紀錄清單 ──────────────────────────────────────────────────────────────────
for t in filtered:
    action = t.get("action", "")
    ticker = t.get("ticker", "")
    term = t.get("term", "")
    trade_date = t.get("date", "")
    shares = t.get("shares", 0)
    price = t.get("price", 0)
    fee = t.get("fee", 0)
    reason = t.get("reason", "")
    note = t.get("note", "")
    page_id = t.get("page_id", "")

    action_label = ACTION_LABELS.get(action, action)
    term_label = TERM_LABELS.get(term, term)
    color = ACTION_COLORS.get(action, "#AAAAAA")

    # 現金入出金的標題格式不同
    if action in ("deposit", "withdraw"):
        title = f"{trade_date}　{action_label}　${price:,.0f}"
    else:
        title = f"{trade_date}　{action_label} {ticker}　{shares:,.0f} 股 @ ${price:,.2f}　（{term_label}）"

    with st.expander(title, expanded=False):
        detail_col, del_col = st.columns([5, 1])

        with detail_col:
            if action in ("deposit", "withdraw"):
                st.markdown(f"**金額：** ${price:,.0f}")
            else:
                c1, c2, c3 = st.columns(3)
                c1.metric("成交金額", f"${shares * price:,.0f}")
                c2.metric("手續費", f"${fee:,.0f}")
                c3.markdown(
                    f"<div style='font-size:1.05em;font-weight:600;"
                    f"color:{color};padding-top:8px;'>{action_label}｜{term_label}</div>",
                    unsafe_allow_html=True,
                )
            if reason:
                st.markdown(f"**理由：** {reason}")
            if note:
                st.markdown(f"**備註：** {note}")

        with del_col:
            if st.session_state.confirm_delete == page_id:
                st.warning("確定刪除？")
                if st.button("確定", key=f"confirm_{page_id}", type="primary"):
                    try:
                        delete_trade(page_id)
                        st.session_state.confirm_delete = None
                        st.cache_data.clear()
                        st.success("已刪除")
                        st.rerun()
                    except Exception as e:
                        st.error(f"刪除失敗：{e}")
                if st.button("取消", key=f"cancel_{page_id}"):
                    st.session_state.confirm_delete = None
                    st.rerun()
            else:
                if st.button("🗑️ 刪除", key=f"del_{page_id}"):
                    st.session_state.confirm_delete = page_id
                    st.rerun()

# ── 匯出 CSV ──────────────────────────────────────────────────────────────────
if filtered:
    st.divider()
    df_export = pd.DataFrame(filtered).drop(columns=["page_id"], errors="ignore")
    df_export["action"] = df_export["action"].map(ACTION_LABELS).fillna(df_export["action"])
    df_export["term"] = df_export["term"].map(TERM_LABELS).fillna(df_export["term"])
    df_export = df_export.rename(columns={
        "date": "日期", "ticker": "股票", "action": "操作",
        "term": "期別", "shares": "股數", "price": "成交價",
        "fee": "手續費", "reason": "理由", "note": "備註", "name": "名稱",
    })
    st.download_button(
        "⬇️ 匯出 CSV",
        data=df_export.to_csv(index=False, encoding="utf-8-sig"),
        file_name="交易紀錄.csv",
        mime="text/csv",
    )
