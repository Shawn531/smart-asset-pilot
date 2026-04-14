"""
個股走勢圖
- K 線蠟燭圖 + 移動均線（MA5/MA20/MA60）
- 買入/賣出標記點
- 停損/停利水平線
- 投組報酬率 vs 大盤（^TWII）折線圖
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import date, timedelta

from utils.notion_loader import fetch_trades
from utils.price_fetcher import get_history

st.set_page_config(page_title="走勢圖", page_icon="📈", layout="wide")

st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
</style>
""", unsafe_allow_html=True)

COLOR_UP = "#E05C5C"
COLOR_DOWN = "#4CAF82"

# ── 側邊欄設定 ────────────────────────────────────────────────────────────────
st.title("📈 個股走勢")

@st.cache_data(ttl=300)
def load_trades():
    return fetch_trades()

try:
    trades = load_trades()
except Exception as e:
    st.error(f"無法載入交易紀錄：{e}")
    st.stop()

# 取出所有交易過的股票
tickers = sorted(set(t["ticker"] for t in trades if t["ticker"]))
if not tickers:
    st.info("尚無交易紀錄，請先新增交易。")
    st.stop()

with st.sidebar:
    st.header("設定")
    selected_ticker = st.selectbox("選擇股票", tickers)

    kline_period = st.radio("K 線週期", ["日K", "週K", "月K"], horizontal=True)
    interval_map = {"日K": "1d", "週K": "1wk", "月K": "1mo"}
    interval = interval_map[kline_period]

    period_options = {"3 個月": 90, "6 個月": 180, "1 年": 365, "2 年": 730, "5 年": 1825}
    period_label = st.selectbox("時間區間", list(period_options.keys()), index=2)
    period_days = period_options[period_label]

    show_ma5 = st.checkbox("MA5", value=True)
    show_ma20 = st.checkbox("MA20", value=True)
    show_ma60 = st.checkbox("MA60", value=False)

    st.divider()
    st.subheader("停損/停利線")
    target_price = st.number_input("目標價（停利）", min_value=0.0, value=0.0, step=1.0, format="%.2f")
    stop_loss = st.number_input("停損價", min_value=0.0, value=0.0, step=1.0, format="%.2f")

# ── 載入歷史資料 ──────────────────────────────────────────────────────────────
start_date = date.today() - timedelta(days=period_days)

@st.cache_data(ttl=300)
def load_ohlc(ticker: str, start: str, interval: str):
    return get_history(ticker, start=start, interval=interval)

with st.spinner(f"載入 {selected_ticker} 歷史資料..."):
    df = load_ohlc(selected_ticker, str(start_date), interval)

if df.empty:
    st.warning(f"無法取得 {selected_ticker} 的歷史資料")
    st.stop()

# ── 計算均線 ──────────────────────────────────────────────────────────────────
df["MA5"] = df["Close"].rolling(5).mean()
df["MA20"] = df["Close"].rolling(20).mean()
df["MA60"] = df["Close"].rolling(60).mean()

# ── 取該股交易紀錄（當前時間區間內）────────────────────────────────────────
ticker_trades = [
    t for t in trades
    if t["ticker"] == selected_ticker and t["date"] >= str(start_date)
]

# ── 繪圖 ──────────────────────────────────────────────────────────────────────
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    row_heights=[0.75, 0.25],
    vertical_spacing=0.03,
)

# K 線
fig.add_trace(go.Candlestick(
    x=df.index,
    open=df["Open"],
    high=df["High"],
    low=df["Low"],
    close=df["Close"],
    increasing_line_color=COLOR_UP,
    decreasing_line_color=COLOR_DOWN,
    name="K線",
), row=1, col=1)

# 均線
if show_ma5:
    fig.add_trace(go.Scatter(x=df.index, y=df["MA5"], name="MA5", line=dict(color="#FFD700", width=1)), row=1, col=1)
if show_ma20:
    fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="MA20", line=dict(color="#87CEEB", width=1)), row=1, col=1)
if show_ma60:
    fig.add_trace(go.Scatter(x=df.index, y=df["MA60"], name="MA60", line=dict(color="#DDA0DD", width=1)), row=1, col=1)

# 買入/賣出標記
buy_trades = [t for t in ticker_trades if t["action"] == "buy"]
sell_trades = [t for t in ticker_trades if t["action"] == "sell"]

if buy_trades:
    fig.add_trace(go.Scatter(
        x=[t["date"] for t in buy_trades],
        y=[t["price"] for t in buy_trades],
        mode="markers",
        marker=dict(symbol="triangle-up", size=12, color=COLOR_UP),
        name="買入",
        hovertemplate="買入<br>日期: %{x}<br>價格: $%{y:,.2f}<extra></extra>",
    ), row=1, col=1)

if sell_trades:
    fig.add_trace(go.Scatter(
        x=[t["date"] for t in sell_trades],
        y=[t["price"] for t in sell_trades],
        mode="markers",
        marker=dict(symbol="triangle-down", size=12, color=COLOR_DOWN),
        name="賣出",
        hovertemplate="賣出<br>日期: %{x}<br>價格: $%{y:,.2f}<extra></extra>",
    ), row=1, col=1)

# 停損/停利線
if target_price > 0:
    fig.add_hline(
        y=target_price, line_dash="dash", line_color="#FFD700",
        annotation_text=f"停利 ${target_price:,.2f}", annotation_position="top right",
        row=1, col=1,
    )
if stop_loss > 0:
    fig.add_hline(
        y=stop_loss, line_dash="dash", line_color="#FF6B6B",
        annotation_text=f"停損 ${stop_loss:,.2f}", annotation_position="bottom right",
        row=1, col=1,
    )

# 成交量
colors_vol = [COLOR_UP if c >= o else COLOR_DOWN for c, o in zip(df["Close"], df["Open"])]
fig.add_trace(go.Bar(
    x=df.index, y=df["Volume"],
    marker_color=colors_vol,
    name="成交量",
    showlegend=False,
), row=2, col=1)

fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#0E1117",
    font_color="#FAFAFA",
    xaxis_rangeslider_visible=False,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=600,
    margin=dict(t=20, b=20, l=10, r=10),
)
fig.update_xaxes(gridcolor="#222", zeroline=False)
fig.update_yaxes(gridcolor="#222", zeroline=False)

st.plotly_chart(fig, use_container_width=True)

# ── 報酬率 vs 大盤 ────────────────────────────────────────────────────────────
st.divider()
st.subheader("報酬率 vs 大盤（^TWII）")

@st.cache_data(ttl=3600)
def load_benchmark(start: str):
    return get_history("^TWII", start=start)

with st.spinner("載入大盤資料..."):
    benchmark_df = load_benchmark(str(start_date))

if not benchmark_df.empty and not df.empty:
    # 對齊日期後計算累積報酬率（從起始點 = 0%）
    stock_ret = (df["Close"] / df["Close"].iloc[0] - 1) * 100
    bench_ret = (benchmark_df["Close"] / benchmark_df["Close"].iloc[0] - 1) * 100

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=stock_ret.index, y=stock_ret,
        name=selected_ticker,
        line=dict(color=COLOR_UP, width=2),
        hovertemplate="%{x}: %{y:+.2f}%<extra></extra>",
    ))
    fig2.add_trace(go.Scatter(
        x=bench_ret.index, y=bench_ret,
        name="台股加權 (^TWII)",
        line=dict(color="#888888", width=1.5, dash="dot"),
        hovertemplate="%{x}: %{y:+.2f}%<extra></extra>",
    ))
    fig2.add_hline(y=0, line_color="#555")
    fig2.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0E1117",
        font_color="#FAFAFA",
        yaxis=dict(ticksuffix="%", gridcolor="#222"),
        xaxis=dict(gridcolor="#222"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=280,
        margin=dict(t=10, b=10, l=10, r=10),
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("無法載入大盤資料")
