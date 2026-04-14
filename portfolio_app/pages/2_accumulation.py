"""
資產累積時間軸
Stacked area chart：現金 / 長期 / 中期 / 短期市值 / 已實現損益
追蹤長期財富成長曲線
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import date

from utils.notion_loader import fetch_trades
from utils.price_fetcher import get_multi_history
from utils.pnl_calculator import compute_accumulation_history

st.set_page_config(page_title="資產累積", page_icon="📉", layout="wide")

st.title("📉 資產累積時間軸")
st.caption("每日持倉市值的歷史堆疊圖，追蹤長期財富成長曲線。")

# ── 載入資料 ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_accumulation():
    trades = fetch_trades()
    if not trades:
        return pd.DataFrame(), []

    tickers = list(set(t["ticker"] for t in trades if t["ticker"]))
    start = min(t["date"] for t in trades if t["date"])

    price_histories = get_multi_history(tickers, start=start)
    cash = float(st.secrets.get("CASH_BALANCE", 0))
    df = compute_accumulation_history(trades, price_histories, cash_balance=cash)
    return df, trades

with st.spinner("計算歷史資產累積（首次載入需要較長時間）..."):
    try:
        acc_df, trades = load_accumulation()
    except Exception as e:
        st.error(f"計算失敗：{e}")
        st.stop()

if acc_df.empty:
    st.info("尚無交易紀錄，請先新增交易。")
    st.stop()

# ── 側邊欄：視角切換 ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("設定")
    view_mode = st.radio(
        "顯示模式",
        ["長/中/短期分開", "合計折線"],
        index=0,
    )
    show_realized = st.checkbox("顯示已實現損益", value=True)
    show_cash = st.checkbox("顯示現金", value=True)

# ── 繪製 Stacked Area Chart ───────────────────────────────────────────────────
fig = go.Figure()

if view_mode == "長/中/短期分開":
    # 現金
    if show_cash:
        fig.add_trace(go.Scatter(
            x=acc_df.index, y=acc_df["cash"],
            name="現金",
            stackgroup="one",
            fillcolor="rgba(102,102,102,0.6)",
            line=dict(color="rgba(102,102,102,0.8)", width=1),
            hovertemplate="現金<br>%{x}: $%{y:,.0f}<extra></extra>",
        ))

    # 已實現損益
    if show_realized:
        fig.add_trace(go.Scatter(
            x=acc_df.index, y=acc_df["realized_pnl"].clip(lower=0),
            name="已實現損益",
            stackgroup="one",
            fillcolor="rgba(212,175,55,0.5)",
            line=dict(color="rgba(212,175,55,0.8)", width=1),
            hovertemplate="已實現<br>%{x}: $%{y:,.0f}<extra></extra>",
        ))

    # 短期
    fig.add_trace(go.Scatter(
        x=acc_df.index, y=acc_df["short_value"],
        name="短期部位",
        stackgroup="one",
        fillcolor="rgba(157,195,230,0.6)",
        line=dict(color="rgba(157,195,230,0.8)", width=1),
        hovertemplate="短期<br>%{x}: $%{y:,.0f}<extra></extra>",
    ))

    # 中期
    fig.add_trace(go.Scatter(
        x=acc_df.index, y=acc_df["mid_value"],
        name="中期部位",
        stackgroup="one",
        fillcolor="rgba(91,155,213,0.6)",
        line=dict(color="rgba(91,155,213,0.8)", width=1),
        hovertemplate="中期<br>%{x}: $%{y:,.0f}<extra></extra>",
    ))

    # 長期
    fig.add_trace(go.Scatter(
        x=acc_df.index, y=acc_df["long_value"],
        name="長期部位",
        stackgroup="one",
        fillcolor="rgba(68,114,196,0.7)",
        line=dict(color="rgba(68,114,196,0.9)", width=1),
        hovertemplate="長期<br>%{x}: $%{y:,.0f}<extra></extra>",
    ))

else:
    # 合計折線
    fig.add_trace(go.Scatter(
        x=acc_df.index, y=acc_df["total"],
        name="總資產",
        fill="tozeroy",
        fillcolor="rgba(68,114,196,0.3)",
        line=dict(color="#4472C4", width=2),
        hovertemplate="總資產<br>%{x}: $%{y:,.0f}<extra></extra>",
    ))

fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0E1117",
    font_color="#FAFAFA",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(
        tickprefix="$",
        tickformat=",",
        gridcolor="#222",
    ),
    xaxis=dict(gridcolor="#222"),
    height=480,
    margin=dict(t=20, b=20, l=10, r=10),
)
st.plotly_chart(fig, use_container_width=True)

# ── 摘要數字 ──────────────────────────────────────────────────────────────────
if not acc_df.empty:
    latest = acc_df.iloc[-1]
    earliest = acc_df.iloc[0]
    total_growth = latest["total"] - earliest["total"]
    total_growth_pct = (total_growth / earliest["total"] * 100) if earliest["total"] > 0 else 0.0

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("目前總資產", f"${latest['total']:,.0f}")
    c2.metric("期間成長", f"${total_growth:,.0f}", delta=f"{total_growth_pct:+.1f}%")
    c3.metric("累積已實現損益", f"${latest['realized_pnl']:,.0f}")
    c4.metric("追蹤天數", f"{len(acc_df)} 個交易日")
