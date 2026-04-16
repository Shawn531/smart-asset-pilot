"""
交易紀錄
歷史交易清單，支援篩選、多選刪除、編輯、匯出 CSV
"""

import streamlit as st
import pandas as pd
from datetime import date

from utils.notion_loader import fetch_trades, delete_trade, update_trade
from utils.ticker_names import get_name
from utils.auth import require_login

st.set_page_config(page_title="交易紀錄", page_icon="📋", layout="wide")
current_user = require_login()

st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
</style>
""", unsafe_allow_html=True)

st.title("📋 交易紀錄")

TERM_LABELS = {"long": "長期", "mid": "中期", "short": "短期"}
TERM_OPTIONS_REVERSE = {"長期": "long", "中期": "mid", "短期": "short"}
ACTION_LABELS = {
    "buy": "買入", "sell": "賣出",
    "deposit": "入金", "withdraw": "出金",
}
ACTION_LABELS_REVERSE = {v: k for k, v in ACTION_LABELS.items()}
ACTION_COLORS = {
    "buy": "#E05C5C", "sell": "#4CAF82",
    "deposit": "#FFD700", "withdraw": "#AAAAAA",
}

@st.cache_data(ttl=300)
def load_trades(user: str):
    return fetch_trades(user)

with st.spinner("載入交易紀錄..."):
    try:
        trades = load_trades(current_user)
    except Exception as e:
        st.error(f"無法載入資料：{e}")
        st.stop()

if not trades:
    st.info("尚無交易紀錄，請先至「新增交易」頁面新增。")
    st.stop()

# ── 篩選器 ────────────────────────────────────────────────────────────────────
all_tickers = sorted(set(t["ticker"] for t in trades if t["ticker"] and t["ticker"] != "CASH"))
all_months = sorted(set(
    t["date"][:7] for t in trades if t["date"] and len(t["date"]) >= 7
), reverse=True)

fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 1])
with fc1:
    selected_tickers = st.multiselect("篩選股票", ["CASH"] + all_tickers, default=[])
with fc2:
    selected_actions = st.multiselect(
        "篩選類型",
        options=list(ACTION_LABELS.keys()),
        format_func=lambda x: ACTION_LABELS.get(x, x),
        default=[],
    )
with fc3:
    selected_months = st.multiselect("篩選月份", all_months, default=[], placeholder="全部月份")
with fc4:
    sort_order = st.selectbox("排序", ["最新在前", "最舊在前"])

filtered = trades
if selected_tickers:
    filtered = [t for t in filtered if t["ticker"] in selected_tickers]
if selected_actions:
    filtered = [t for t in filtered if t["action"] in selected_actions]
if selected_months:
    filtered = [t for t in filtered if t.get("date", "")[:7] in selected_months]
filtered = sorted(filtered, key=lambda x: x["date"] or "", reverse=(sort_order == "最新在前"))

st.caption(f"共 {len(filtered)} 筆紀錄")

# ── 操作模式 ──────────────────────────────────────────────────────────────────
bulk_mode = st.toggle("🗑️ 批量刪除模式", value=False)

# ══════════════════════════════════════════════════════════════════════════════
# 批量刪除模式
# ══════════════════════════════════════════════════════════════════════════════
if bulk_mode:
    # 全選 / 取消全選
    sa_col1, sa_col2, _ = st.columns([1, 1, 8])
    with sa_col1:
        if st.button("全選", use_container_width=True):
            for t in filtered:
                st.session_state[f"bulk_{t['page_id']}"] = True
            st.rerun()
    with sa_col2:
        if st.button("取消全選", use_container_width=True):
            for t in filtered:
                st.session_state[f"bulk_{t['page_id']}"] = False
            st.rerun()

    st.caption("勾選要刪除的紀錄，再按確認按鈕一次刪除。")

    selected_ids: list[str] = []

    for t in filtered:
        action = t.get("action", "")
        ticker = t.get("ticker", "")
        trade_date = t.get("date", "")
        shares = t.get("shares", 0)
        price = t.get("price", 0)
        page_id = t.get("page_id", "")
        action_label = ACTION_LABELS.get(action, action)
        name = get_name(ticker) if ticker and ticker != "CASH" else ticker
        color = ACTION_COLORS.get(action, "#AAAAAA")

        if action in ("deposit", "withdraw"):
            desc = f"{trade_date}　{action_label}　${price:,.0f}"
        else:
            name_str = f"{name} ({ticker})" if name != ticker else ticker
            desc = f"{trade_date}　{action_label} {name_str}　{shares:,.0f} 股 @ ${price:,.2f}"

        col_check, col_info = st.columns([1, 14])
        with col_check:
            checked = st.checkbox("", key=f"bulk_{page_id}", label_visibility="collapsed")
        with col_info:
            st.markdown(
                f"<span style='color:{color};font-weight:600'>{action_label}</span>　"
                f"<span style='color:#CCC'>{desc}</span>",
                unsafe_allow_html=True,
            )
        if checked:
            selected_ids.append(page_id)

    if selected_ids:
        st.divider()
        st.warning(f"已選取 {len(selected_ids)} 筆，刪除後無法復原。")
        if st.button(f"確認刪除 {len(selected_ids)} 筆", type="primary", use_container_width=True):
            prog = st.progress(0)
            for i, pid in enumerate(selected_ids):
                try:
                    delete_trade(pid)
                except Exception:
                    pass
                prog.progress((i + 1) / len(selected_ids))
            st.cache_data.clear()
            st.success("刪除完成！")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# 一般模式：展開式紀錄 + 編輯
# ══════════════════════════════════════════════════════════════════════════════
else:
    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = None
    if "editing_id" not in st.session_state:
        st.session_state.editing_id = None

    for t in filtered:
        action = t.get("action", "")
        ticker = t.get("ticker", "")
        term = t.get("term", "long")
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
        name = get_name(ticker) if ticker and ticker != "CASH" else ticker
        name_str = f"{name} ({ticker})" if name != ticker else ticker

        # 標題列：含理由預覽
        reason_preview = ""
        if reason and action not in ("deposit", "withdraw"):
            short = reason[:18] + ("…" if len(reason) > 18 else "")
            reason_preview = f"　｜　{short}"

        if action in ("deposit", "withdraw"):
            title = f"{trade_date}　{action_label}　${price:,.0f}"
        else:
            title = (
                f"{trade_date}　{action_label} {name_str}　"
                f"{shares:,.0f} 股 @ ${price:,.2f}　（{term_label}）"
                f"{reason_preview}"
            )

        with st.expander(title, expanded=False):

            # ── 編輯模式 ──────────────────────────────────────────────────────
            if st.session_state.editing_id == page_id:
                st.caption("✏️ 編輯模式")
                with st.form(key=f"edit_form_{page_id}"):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        e_date = st.date_input(
                            "交易日期",
                            value=date.fromisoformat(trade_date) if trade_date else date.today(),
                        )
                        e_action = st.selectbox(
                            "操作",
                            list(ACTION_LABELS.keys()),
                            format_func=lambda x: ACTION_LABELS[x],
                            index=list(ACTION_LABELS.keys()).index(action) if action in ACTION_LABELS else 0,
                        )
                        e_term = st.selectbox(
                            "期別",
                            list(TERM_LABELS.keys()),
                            format_func=lambda x: TERM_LABELS[x],
                            index=list(TERM_LABELS.keys()).index(term) if term in TERM_LABELS else 0,
                        )
                    with e_col2:
                        e_shares = st.number_input("股數", value=float(shares), min_value=0.0, step=1.0, format="%.0f")
                        e_price = st.number_input("成交價", value=float(price), min_value=0.0, step=0.01, format="%.2f")
                        e_fee = st.number_input("手續費", value=float(fee), min_value=0.0, step=1.0, format="%.0f")
                    e_ticker = st.text_input("股票代號", value=ticker).strip().upper()
                    e_reason = st.text_area("理由", value=reason, height=72)
                    e_note = st.text_area("備註", value=note, height=60)

                    s_col, c_col = st.columns(2)
                    with s_col:
                        saved = st.form_submit_button("💾 儲存", type="primary", use_container_width=True)
                    with c_col:
                        cancelled = st.form_submit_button("取消", use_container_width=True)

                if saved:
                    try:
                        update_trade(
                            page_id=page_id,
                            ticker=e_ticker,
                            action=e_action,
                            term=e_term,
                            trade_date=e_date,
                            shares=e_shares,
                            price=e_price,
                            fee=e_fee,
                            reason=e_reason.strip(),
                            note=e_note.strip(),
                        )
                        st.session_state.editing_id = None
                        st.cache_data.clear()
                        st.success("已更新！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"更新失敗：{e}")
                elif cancelled:
                    st.session_state.editing_id = None
                    st.rerun()

            # ── 一般顯示 ──────────────────────────────────────────────────────
            else:
                detail_col, btn_col = st.columns([5, 1])

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

                with btn_col:
                    # 編輯按鈕
                    if st.button("✏️", key=f"edit_{page_id}", help="編輯此筆"):
                        st.session_state.editing_id = page_id
                        st.session_state.confirm_delete = None
                        st.rerun()

                    # 刪除按鈕
                    if st.session_state.confirm_delete == page_id:
                        st.warning("確定？")
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
                        if st.button("🗑️", key=f"del_{page_id}", help="刪除此筆"):
                            st.session_state.confirm_delete = page_id
                            st.session_state.editing_id = None
                            st.rerun()

# ── 匯出 CSV ──────────────────────────────────────────────────────────────────
if filtered and not bulk_mode:
    st.divider()
    df_export = pd.DataFrame(filtered).drop(columns=["page_id"], errors="ignore")
    df_export["action"] = df_export["action"].map(ACTION_LABELS).fillna(df_export["action"])
    df_export["term"] = df_export["term"].map(TERM_LABELS).fillna(df_export["term"])
    df_export.insert(2, "名稱", df_export["ticker"].apply(get_name))
    df_export = df_export.rename(columns={
        "date": "日期", "ticker": "股票代號", "action": "操作",
        "term": "期別", "shares": "股數", "price": "成交價",
        "fee": "手續費", "reason": "理由", "note": "備註", "name": "Notion名稱",
    })
    st.download_button(
        "⬇️ 匯出 CSV",
        data=df_export.to_csv(index=False, encoding="utf-8-sig"),
        file_name="交易紀錄.csv",
        mime="text/csv",
    )
