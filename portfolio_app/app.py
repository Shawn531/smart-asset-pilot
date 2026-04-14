"""
投資組合總覽
主頁面：三個 Tab（長期/中期/短期）持倉卡片 + Metric cards + 圖表
"""

import streamlit as st
import plotly.graph_objects as go

from utils.notion_loader import fetch_trades
from utils.price_fetcher import get_current_prices
from utils.pnl_calculator import compute_positions, compute_summary, compute_cash, TERM_LABELS

st.set_page_config(
    page_title="投資組合",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 字體加大 CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
.stMetric label { font-size: 0.95rem !important; }
.stMetric [data-testid="metric-container"] > div { font-size: 1.5rem !important; }
div[data-testid="stTab"] button { font-size: 1rem !important; }
</style>
""", unsafe_allow_html=True)

# ── 顏色設定（台灣慣例：紅漲綠跌）─────────────────────────────────────────
COLOR_UP = "#E05C5C"
COLOR_DOWN = "#4CAF82"
COLOR_NEUTRAL = "#AAAAAA"
TERM_COLORS = {"long": "#4472C4", "mid": "#5B9BD5", "short": "#9DC3E6"}

STOCK_COLORS = [
    "#4472C4", "#E05C5C", "#FFD700", "#4CAF82", "#DDA0DD",
    "#FF8C00", "#00CED1", "#FF69B4", "#7CFC00", "#DC143C",
]


def pnl_color(value: float) -> str:
    if value > 0:
        return COLOR_UP
    if value < 0:
        return COLOR_DOWN
    return COLOR_NEUTRAL


def pnl_arrow(value: float) -> str:
    if value > 0:
        return "▲"
    if value < 0:
        return "▼"
    return "─"


# ── 側邊欄 ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 設定")
    if st.button("🔄 重新整理資料"):
        st.cache_data.clear()
        st.rerun()

# ── 資料載入（快取 5 分鐘）───────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    trades = fetch_trades()
    positions = compute_positions(trades)
    tickers = list(positions.keys())
    prices = get_current_prices(tickers) if tickers else {}
    summary = compute_summary(positions, prices)
    cash = compute_cash(trades)
    return trades, positions, prices, summary, cash


st.title("📊 投資組合總覽")

with st.spinner("載入資料中..."):
    try:
        trades, positions, prices, summary, cash = load_data()
    except Exception as e:
        st.error(f"資料載入失敗：{e}")
        st.stop()

total_assets = summary["total_market_value"] + cash

# ── 頂部 Metric Cards ────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("總資產（含現金）", f"${total_assets:,.0f}")
col2.metric("持倉市值", f"${summary['total_market_value']:,.0f}")
unrealized = summary["total_unrealized_pnl"]
col3.metric(
    "未實現損益",
    f"${unrealized:,.0f}",
    delta=f"{unrealized / summary['total_cost'] * 100:.1f}%" if summary["total_cost"] > 0 else "0%",
)
col4.metric("已實現損益", f"${summary['total_realized_pnl']:,.0f}")

st.divider()

# ── 持倉分 Tab 顯示 ──────────────────────────────────────────────────────────
tabs = st.tabs(["📈 長期", "📊 中期", "⚡ 短期"])

for tab, term_key in zip(tabs, ["long", "mid", "short"]):
    with tab:
        term_label = TERM_LABELS[term_key]
        term_positions = {
            t: d for t, d in summary["by_ticker"].items()
            if d["term"] == term_key
        }

        if not term_positions:
            st.info(f"目前無{term_label}部位")
            continue

        term_data = summary["by_term"][term_key]
        tm_val = term_data["market_value"]
        tm_pnl = term_data["unrealized_pnl"]
        tm_pnl_pct = (tm_pnl / term_data["cost"] * 100) if term_data["cost"] > 0 else 0.0

        st.markdown(
            f"**{term_label}小計：** 市值 `${tm_val:,.0f}` ｜ "
            f"未實現損益 <span style='color:{pnl_color(tm_pnl)}'>"
            f"{pnl_arrow(tm_pnl)} ${abs(tm_pnl):,.0f} ({tm_pnl_pct:+.1f}%)</span>",
            unsafe_allow_html=True,
        )

        ticker_list = list(term_positions.keys())
        for i in range(0, len(ticker_list), 2):
            cols = st.columns(2)
            for j, ticker in enumerate(ticker_list[i: i + 2]):
                d = term_positions[ticker]
                upnl = d["unrealized_pnl"]
                upnl_pct = d["unrealized_pct"]
                color = pnl_color(upnl)
                arrow = pnl_arrow(upnl)

                with cols[j]:
                    st.markdown(
                        f"""
<div style="background:#1C1C2E;border-radius:12px;padding:16px 18px;margin-bottom:10px;">
  <div style="font-size:1.1em;font-weight:700;margin-bottom:6px;">
    {ticker}
    <span style="font-size:0.82em;color:#999;font-weight:400;margin-left:8px;">
      {term_label} ・ 持有 {d['holding_days']} 天
    </span>
  </div>
  <div style="font-size:0.95em;color:#CCC;margin-bottom:8px;">
    股數: <b>{d['shares']:,.0f}</b> ｜
    成本: <b>${d['avg_cost']:,.2f}</b> ｜
    現價: <b>${d['current_price']:,.2f}</b>
  </div>
  <div style="font-size:1.2em;font-weight:600;color:{color};">
    {arrow} ${abs(upnl):,.0f} &nbsp;({upnl_pct:+.1f}%)
  </div>
  <div style="font-size:0.85em;color:#888;margin-top:4px;">
    市值: ${d['market_value']:,.0f}
  </div>
</div>
""",
                        unsafe_allow_html=True,
                    )

st.divider()

# ── 圖表區 ───────────────────────────────────────────────────────────────────
if summary["by_ticker"]:
    chart_col1, chart_col2 = st.columns([1, 1])

    with chart_col1:
        st.subheader("資產配置（個股）")

        # 現金 + 各個股市值
        pie_labels = []
        pie_values = []
        pie_colors = []

        if cash > 0:
            pie_labels.append("現金")
            pie_values.append(cash)
            pie_colors.append("#555555")

        for idx, (ticker, d) in enumerate(summary["by_ticker"].items()):
            mv = d["market_value"]
            if mv > 0:
                pie_labels.append(ticker)
                pie_values.append(mv)
                pie_colors.append(STOCK_COLORS[idx % len(STOCK_COLORS)])

        fig_pie = go.Figure(go.Pie(
            labels=pie_labels,
            values=pie_values,
            marker_colors=pie_colors,
            hole=0.4,
            textinfo="label+percent",
            hovertemplate="%{label}<br>$%{value:,.0f}<extra></extra>",
        ))
        fig_pie.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#FAFAFA", size=14),
            showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            height=320,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart_col2:
        st.subheader("個股損益")
        tickers_sorted = sorted(
            summary["by_ticker"].keys(),
            key=lambda t: summary["by_ticker"][t]["unrealized_pct"],
        )
        bar_colors = [
            COLOR_UP if summary["by_ticker"][t]["unrealized_pct"] >= 0 else COLOR_DOWN
            for t in tickers_sorted
        ]
        fig_bar = go.Figure(go.Bar(
            x=[summary["by_ticker"][t]["unrealized_pct"] for t in tickers_sorted],
            y=tickers_sorted,
            orientation="h",
            marker_color=bar_colors,
            text=[f"{summary['by_ticker'][t]['unrealized_pct']:+.1f}%" for t in tickers_sorted],
            textposition="outside",
            textfont=dict(size=14),
            hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
        ))
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#0E1117",
            font=dict(color="#FAFAFA", size=14),
            xaxis=dict(ticksuffix="%", gridcolor="#333"),
            yaxis=dict(gridcolor="#333", tickfont=dict(size=14)),
            margin=dict(t=10, b=10, l=10, r=70),
            height=320,
        )
        fig_bar.add_vline(x=0, line_color="#555")
        st.plotly_chart(fig_bar, use_container_width=True)

st.caption("資料每 5 分鐘自動快取。側邊欄按「重新整理資料」立即更新。")
