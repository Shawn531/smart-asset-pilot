"""
個股走勢圖 + 觀察清單
- K 線蠟燭圖 + 移動均線（MA5/MA20/MA60）
- 買入/賣出標記點、停損/停利水平線
- 觀察清單即時報價
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import yfinance as yf
from datetime import date, timedelta

from utils.notion_loader import fetch_trades
from utils.price_fetcher import get_history
from utils.pnl_calculator import compute_positions
from utils.ticker_names import get_name, TICKER_TO_NAME
from utils.auth import require_login

st.set_page_config(page_title="走勢圖", page_icon="📈", layout="wide")
current_user = require_login()

st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
</style>
""", unsafe_allow_html=True)

COLOR_UP = "#E05C5C"
COLOR_DOWN = "#4CAF82"

st.title("📈 走勢圖 / 觀察清單")

# ── 主 Tab ───────────────────────────────────────────────────────────────────
tab_chart, tab_watch = st.tabs(["📈 個股走勢", "👁️ 觀察清單"])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1：個股走勢
# ══════════════════════════════════════════════════════════════════════════════
with tab_chart:

    @st.cache_data(ttl=300)
    def load_trades(user: str):
        return fetch_trades(user)

    try:
        trades = load_trades(current_user)
    except Exception as e:
        st.error(f"無法載入交易紀錄：{e}")
        st.stop()

    if not trades:
        st.info("尚無交易紀錄，請先新增交易。")
        st.stop()

    # 計算當前持倉（trades 本身是 list of dict，直接傳入，不需要 cache key trick）
    positions = compute_positions(trades)
    active_set = set(positions.keys())

    # 所有交易過的股票（排除 CASH）
    all_traded = sorted(set(
        t["ticker"] for t in trades
        if t["ticker"] and t["ticker"] != "CASH" and t["action"] in ("buy", "sell")
    ))

    # ── 側邊欄設定 ────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("走勢圖設定")

        ticker_scope = st.radio(
            "顯示股票範圍",
            ["當前持倉", "全部交易過"],
            horizontal=True,
        )

        if ticker_scope == "當前持倉":
            ticker_pool = sorted(t for t in all_traded if t in active_set) or all_traded
        else:
            ticker_pool = all_traded

        if not ticker_pool:
            st.warning("無可選股票")
            st.stop()

        _preselect = st.session_state.pop("chart_ticker", None)
        _default_idx = ticker_pool.index(_preselect) if _preselect and _preselect in ticker_pool else 0
        selected_ticker = st.selectbox(
            "選擇股票",
            ticker_pool,
            index=_default_idx,
            format_func=lambda t: f"{get_name(t)}  {t}" if get_name(t) != t else t,
        )

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

    # ── 頁面標題 ──────────────────────────────────────────────────────────────
    name = get_name(selected_ticker)
    title_str = f"{name}（{selected_ticker}）" if name != selected_ticker else selected_ticker
    badge = "🟢 持倉中" if selected_ticker in active_set else "⚪ 已了結"
    st.subheader(f"{title_str}　{badge}")

    # ── 載入歷史資料 ──────────────────────────────────────────────────────────
    start_date = date.today() - timedelta(days=period_days)

    @st.cache_data(ttl=300)
    def load_ohlc(ticker: str, start: str, iv: str):
        return get_history(ticker, start=start, interval=iv)

    with st.spinner(f"載入 {selected_ticker} 資料..."):
        df = load_ohlc(selected_ticker, str(start_date), interval)

    if df.empty:
        st.warning(f"無法取得 {selected_ticker} 的歷史資料")
        st.stop()

    df["MA5"]  = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    ticker_trades = [
        t for t in trades
        if t["ticker"] == selected_ticker and t.get("date", "") >= str(start_date)
    ]

    # ── K 線圖 ────────────────────────────────────────────────────────────────
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.75, 0.25], vertical_spacing=0.03,
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        increasing_line_color=COLOR_UP, decreasing_line_color=COLOR_DOWN, name="K線",
    ), row=1, col=1)

    if show_ma5:
        fig.add_trace(go.Scatter(x=df.index, y=df["MA5"],  name="MA5",  line=dict(color="#FFD700", width=1)), row=1, col=1)
    if show_ma20:
        fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="MA20", line=dict(color="#87CEEB", width=1)), row=1, col=1)
    if show_ma60:
        fig.add_trace(go.Scatter(x=df.index, y=df["MA60"], name="MA60", line=dict(color="#DDA0DD", width=1)), row=1, col=1)

    buy_tr  = [t for t in ticker_trades if t["action"] == "buy"]
    sell_tr = [t for t in ticker_trades if t["action"] == "sell"]
    if buy_tr:
        fig.add_trace(go.Scatter(
            x=[t["date"] for t in buy_tr], y=[t["price"] for t in buy_tr],
            mode="markers",
            marker=dict(symbol="triangle-up", size=14, color="#FFD700",
                        line=dict(color="#000", width=1)),
            name="買入", hovertemplate="買入<br>%{x}<br>$%{y:,.2f}<extra></extra>",
        ), row=1, col=1)
    if sell_tr:
        fig.add_trace(go.Scatter(
            x=[t["date"] for t in sell_tr], y=[t["price"] for t in sell_tr],
            mode="markers",
            marker=dict(symbol="triangle-down", size=14, color="#00E5FF",
                        line=dict(color="#000", width=1)),
            name="賣出", hovertemplate="賣出<br>%{x}<br>$%{y:,.2f}<extra></extra>",
        ), row=1, col=1)

    if target_price > 0:
        fig.add_hline(y=target_price, line_dash="dash", line_color="#FFD700",
                      annotation_text=f"停利 ${target_price:,.2f}", annotation_position="top right", row=1, col=1)
    if stop_loss > 0:
        fig.add_hline(y=stop_loss, line_dash="dash", line_color="#FF6B6B",
                      annotation_text=f"停損 ${stop_loss:,.2f}", annotation_position="bottom right", row=1, col=1)

    vol_colors = [COLOR_UP if c >= o else COLOR_DOWN for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=vol_colors, name="成交量", showlegend=False), row=2, col=1)

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0E1117", font_color="#FAFAFA",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=600, margin=dict(t=20, b=20, l=10, r=10),
    )
    fig.update_xaxes(gridcolor="#222", zeroline=False)
    fig.update_yaxes(gridcolor="#222", zeroline=False)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── 報酬率 vs 大盤 ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("報酬率 vs 大盤（^TWII）")

    @st.cache_data(ttl=3600)
    def load_benchmark(start: str):
        return get_history("^TWII", start=start)

    with st.spinner("載入大盤資料..."):
        bench_df = load_benchmark(str(start_date))

    if not bench_df.empty and not df.empty:
        stock_ret = (df["Close"] / df["Close"].iloc[0] - 1) * 100
        bench_ret  = (bench_df["Close"] / bench_df["Close"].iloc[0] - 1) * 100
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=stock_ret.index, y=stock_ret, name=name if name != selected_ticker else selected_ticker,
                                  line=dict(color=COLOR_UP, width=2), hovertemplate="%{x}: %{y:+.2f}%<extra></extra>"))
        fig2.add_trace(go.Scatter(x=bench_ret.index, y=bench_ret, name="台股加權 (^TWII)",
                                  line=dict(color="#888888", width=1.5, dash="dot"), hovertemplate="%{x}: %{y:+.2f}%<extra></extra>"))
        fig2.add_hline(y=0, line_color="#555")
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0E1117", font_color="#FAFAFA",
            yaxis=dict(ticksuffix="%", gridcolor="#222"), xaxis=dict(gridcolor="#222"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=280, margin=dict(t=10, b=10, l=10, r=10),
        )
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("無法載入大盤資料")


# ══════════════════════════════════════════════════════════════════════════════
# Tab 2：觀察清單
# ══════════════════════════════════════════════════════════════════════════════
with tab_watch:
    st.subheader("觀察清單")

    default_watchlist = ["2330.TW", "2308.TW", "0050.TW", "00878.TW", "NVDA"]
    try:
        watchlist = list(st.secrets.get("WATCHLIST", default_watchlist))
    except Exception:
        watchlist = default_watchlist

    if "watchlist_extra" not in st.session_state:
        st.session_state.watchlist_extra = []

    add_col, btn_col = st.columns([4, 1])
    with add_col:
        new_ticker = st.text_input(
            "新增代號（本次有效）", placeholder="例：2454.TW 或 AAPL",
            label_visibility="collapsed", key="watch_input",
        ).strip().upper()
    with btn_col:
        if st.button("新增", key="watch_add", use_container_width=True):
            if new_ticker and new_ticker not in watchlist and new_ticker not in st.session_state.watchlist_extra:
                st.session_state.watchlist_extra.append(new_ticker)
                st.rerun()

    all_watch = watchlist + st.session_state.watchlist_extra

    @st.cache_data(ttl=120)
    def fetch_watch(tickers: tuple) -> list[dict]:
        results = []
        for tk in tickers:
            try:
                info = yf.Ticker(tk).fast_info
                p = info.last_price
                prev = info.previous_close
                if p is None or prev is None:
                    raise ValueError
                chg = p - prev
                pct = chg / prev * 100
                results.append({"ticker": tk, "price": float(p), "change": float(chg), "pct": float(pct), "ok": True})
            except Exception:
                results.append({"ticker": tk, "ok": False})
        return results

    if st.button("🔄 重新整理觀察清單", key="watch_refresh"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("載入報價..."):
        watch_data = fetch_watch(tuple(all_watch))

    cols_n = 3
    for i in range(0, len(watch_data), cols_n):
        wcols = st.columns(cols_n)
        for j, d in enumerate(watch_data[i: i + cols_n]):
            tk = d["ticker"]
            nm = get_name(tk)
            with wcols[j]:
                if not d["ok"]:
                    st.markdown(
                        f"<div style='background:#1C1C2E;border-radius:10px;padding:12px 14px;margin-bottom:8px'>"
                        f"<b>{nm}</b><br><span style='color:#888;font-size:0.82em'>{tk}</span>"
                        f"<br><span style='color:#666'>無法取得報價</span></div>",
                        unsafe_allow_html=True,
                    )
                    continue
                c = "#E05C5C" if d["change"] > 0 else ("#4CAF82" if d["change"] < 0 else "#AAAAAA")
                arrow = "▲" if d["change"] > 0 else ("▼" if d["change"] < 0 else "─")
                sign = "+" if d["change"] >= 0 else ""
                nm_line = f"<b>{nm}</b>" if nm != tk else f"<b>{tk}</b>"
                tk_line = f"<span style='color:#888;font-size:0.82em'>{tk}</span>" if nm != tk else ""
                st.markdown(
                    f"<div style='background:#1C1C2E;border-radius:10px;padding:12px 14px;margin-bottom:8px'>"
                    f"{nm_line}<br>{tk_line}"
                    f"<div style='font-size:1.4em;font-weight:700;margin-top:4px'>${d['price']:,.2f}</div>"
                    f"<div style='color:{c}'>{arrow} {sign}{d['change']:,.2f}　({sign}{d['pct']:.2f}%)</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    st.caption("固定清單請在 .streamlit/secrets.toml 新增：`WATCHLIST = [\"2330.TW\", \"0050.TW\"]`　報價每 2 分鐘快取。")
