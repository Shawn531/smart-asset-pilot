"""
投資組合總覽
主頁面：三個 Tab（長期/中期/短期）持倉卡片 + Metric cards + 圖表
"""

import streamlit as st
import plotly.graph_objects as go
import yfinance as yf

from utils.pnl_calculator import TERM_LABELS
from utils.ticker_names import get_name
from utils.auth import require_login
from utils.portfolio_loader import load_portfolio
from utils.notion_loader import fetch_watchlist, add_to_watchlist, delete_trade

st.set_page_config(
    page_title="投資組合",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

current_user = require_login()

st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
.stMetric label { font-size: 0.95rem !important; }
.stMetric [data-testid="metric-container"] > div { font-size: 1.4rem !important; }
div[data-testid="stTab"] button { font-size: 1rem !important; }
</style>
""", unsafe_allow_html=True)

COLOR_UP      = "#E05C5C"
COLOR_DOWN    = "#4CAF82"
COLOR_NEUTRAL = "#AAAAAA"

LONG_COLORS  = ["#1a4a90", "#2563c8", "#4472C4", "#6898DA", "#9DC3E6", "#C5DCF0"]
MID_COLORS   = ["#155e40", "#1a8c5e", "#25B87A", "#50CC96", "#85DDB8", "#B0EDD4"]
SHORT_COLORS = ["#7a4a00", "#b36a00", "#E08C00", "#E8A830", "#F0C060", "#F8DC90"]
TERM_PALETTE = {"long": LONG_COLORS, "mid": MID_COLORS, "short": SHORT_COLORS}
TERM_LEGEND_COLOR = {"long": "#4472C4", "mid": "#25B87A", "short": "#E08C00"}


def pnl_color(v: float) -> str:
    return COLOR_UP if v > 0 else (COLOR_DOWN if v < 0 else COLOR_NEUTRAL)


def pnl_arrow(v: float) -> str:
    return "▲" if v > 0 else ("▼" if v < 0 else "─")


with st.sidebar:
    st.header("⚙️ 設定")
    if st.button("🔄 重新整理資料"):
        st.cache_data.clear()
        st.rerun()


st.title("📊 投資組合總覽")

with st.spinner("載入資料中..."):
    try:
        trades, positions, prices, summary, cash, realized_by_ticker, total_buy_cost_by_ticker = load_portfolio(current_user)
    except Exception as e:
        st.error(f"資料載入失敗：{e}")
        st.stop()

total_mv   = summary["total_market_value"]
total_cost = summary["total_cost"]
unrealized = summary["total_unrealized_pnl"]
realized   = summary["total_realized_pnl"]
total_assets = total_mv + cash

# ── 6 格 Metric Cards ────────────────────────────────────────────────────────
r1c1, r1c2, r1c3 = st.columns(3)
r1c1.metric("總資產（現金 + 市值）", f"${total_assets:,.0f}",
            help="現金餘額 = 入金 − 出金 − 買股支出（含手續費）＋ 賣股收入（扣手續費）")
r1c2.metric("現金餘額", f"${cash:,.0f}")
r1c3.metric("持倉市值", f"${total_mv:,.0f}")

r2c1, r2c2, r2c3 = st.columns(3)
r2c1.metric("總成本（含手續費）", f"${total_cost:,.0f}")
upnl_pct = unrealized / total_cost * 100 if total_cost > 0 else 0.0
r2c2.metric("未實現損益（市值 − 成本）", f"${unrealized:,.0f}", delta=f"{upnl_pct:+.1f}%")
r2c3.metric("已實現損益（含平倉）", f"${realized:,.0f}",
            help="FIFO 計算，含完全賣光的股票；手續費已計入成本。")

st.divider()

# ── 觀察清單資料（Tab 用）────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def _load_watch_items_home(user: str) -> list[dict]:
    return fetch_watchlist(user)


@st.cache_data(ttl=120)
def load_watchlist(tickers: tuple) -> list[dict]:
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
            results.append({
                "ticker": tk, "price": float(p),
                "change": float(chg), "pct": float(pct), "ok": True,
            })
        except Exception:
            results.append({"ticker": tk, "ok": False})
    return results


# ── 持倉 Tab ─────────────────────────────────────────────────────────────────
tab_long, tab_mid, tab_short, tab_watch = st.tabs(["📈 長期", "📊 中期", "⚡ 短期", "👁️ 觀察清單"])
for tab, term_key in zip([tab_long, tab_mid, tab_short], ["long", "mid", "short"]):
    with tab:
        term_label = TERM_LABELS[term_key]
        term_pos = {t: d for t, d in summary["by_ticker"].items() if d["term"] == term_key}
        if not term_pos:
            st.info(f"目前無{term_label}部位")
            continue

        td = summary["by_term"][term_key]
        tm_pnl = td["unrealized_pnl"]
        tm_pct = (tm_pnl / td["cost"] * 100) if td["cost"] > 0 else 0.0
        st.markdown(
            f"**{term_label}小計：** 市值 `${td['market_value']:,.0f}` ｜ "
            f"未實現損益 <span style='color:{pnl_color(tm_pnl)}'>"
            f"{pnl_arrow(tm_pnl)} ${abs(tm_pnl):,.0f} ({tm_pct:+.1f}%)</span>",
            unsafe_allow_html=True,
        )

        tlist = list(term_pos.keys())
        for i in range(0, len(tlist), 2):
            cols = st.columns(2)
            for j, ticker in enumerate(tlist[i: i + 2]):
                d = term_pos[ticker]
                upnl = d["unrealized_pnl"]
                color = pnl_color(upnl)
                arrow = pnl_arrow(upnl)
                name = get_name(ticker)
                # 顯示「中文名稱 (代號)」
                if name != ticker:
                    header = f"{name} <span style='color:#888;font-size:0.82em'>({ticker})</span>"
                else:
                    header = ticker

                with cols[j]:
                    st.markdown(f"""
<div style="background:#1C1C2E;border-radius:12px;padding:16px 18px;margin-bottom:4px;">
  <div style="font-size:1.05em;font-weight:700;margin-bottom:6px;">
    {header}
    <span style="font-size:0.8em;color:#888;font-weight:400;margin-left:6px;">{term_label} ・ 持有 {d['holding_days']} 天</span>
  </div>
  <div style="font-size:0.9em;color:#CCC;margin-bottom:6px;">
    股數: <b>{d['shares']:,.0f}</b> ｜ 成本: <b>${d['avg_cost']:,.2f}</b> ｜ 現價: <b>${d['current_price']:,.2f}</b>
  </div>
  <div style="font-size:1.2em;font-weight:600;color:{color};">
    {arrow} ${abs(upnl):,.0f} <span style="font-size:0.82em">({d['unrealized_pct']:+.1f}%)</span>
  </div>
  <div style="font-size:0.82em;color:#888;margin-top:4px;">
    市值: ${d['market_value']:,.0f} ｜ 總成本: ${d['cost_basis']:,.0f}
  </div>
</div>""", unsafe_allow_html=True)
                    if st.button("📈 走勢圖", key=f"goto_chart_{ticker}_{term_key}",
                                 use_container_width=True):
                        st.session_state["chart_ticker"] = ticker
                        st.switch_page("pages/1_charts.py")

st.divider()

# ── 圖表區 ───────────────────────────────────────────────────────────────────
if not summary["by_ticker"]:
    st.caption("尚無持倉，圖表待資料產生後顯示。")
    st.stop()

chart_col1, chart_col2 = st.columns([1, 1])

# ── 圓餅圖 ────────────────────────────────────────────────────────────────────
with chart_col1:
    st.subheader("資產配置")

    # 按期別排序，同期別內按市值大小排
    pie_labels, pie_values, pie_colors_list = [], [], []
    term_idx_cnt = {"long": 0, "mid": 0, "short": 0}

    # 先建立「長→中→短→現金」順序，之後反轉陣列
    # 配合順時針繪製（反轉後從 12 點順時針讀 = 現金→短→中→長
    # 等同於從 12 點逆時針讀 = 長→中→短→現金）
    for term_key in ["long", "mid", "short"]:
        # 同期別按市值由大到小
        group = sorted(
            [(t, d) for t, d in summary["by_ticker"].items()
             if d["term"] == term_key and d["market_value"] > 0],
            key=lambda x: -x[1]["market_value"],
        )
        for ticker, d in group:
            palette = TERM_PALETTE[term_key]
            idx = term_idx_cnt[term_key]
            pie_colors_list.append(palette[idx % len(palette)])
            term_idx_cnt[term_key] = idx + 1
            pie_labels.append(get_name(ticker))
            pie_values.append(d["market_value"])

    if cash > 0:
        pie_labels.append("現金")
        pie_values.append(cash)
        pie_colors_list.append("#555555")

    # 反轉後順時針繪製，視覺等同逆時針長→中→短→現金
    pie_labels     = pie_labels[::-1]
    pie_values     = pie_values[::-1]
    pie_colors_list = pie_colors_list[::-1]

    fig_pie = go.Figure(go.Pie(
        labels=pie_labels,
        values=pie_values,
        marker_colors=pie_colors_list,
        hole=0.44,
        textinfo="percent",
        textposition="inside",
        insidetextfont=dict(size=11),
        hovertemplate="%{label}<br>$%{value:,.0f} (%{percent})<extra></extra>",
        showlegend=False,
        sort=False,
        direction="clockwise",
        rotation=0,
    ))
    fig_pie.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#FAFAFA", size=12),
        margin=dict(t=10, b=10, l=10, r=10),
        height=300,
        annotations=[dict(
            text=f"<b>總市值</b><br>${total_mv:,.0f}",
            x=0.5, y=0.5,
            font=dict(size=12, color="#FAFAFA"),
            showarrow=False, align="center",
        )],
    )
    st.plotly_chart(fig_pie, use_container_width=True, config={"displayModeBar": False})

    # ── 自訂圖例（長/中/短期分組，同組內按市值排序）────────────────────────
    legend_html = []
    for term_key in ["long", "mid", "short"]:
        group = sorted(
            [(t, d) for t, d in summary["by_ticker"].items()
             if d["term"] == term_key and d["market_value"] > 0],
            key=lambda x: -x[1]["market_value"],
        )
        if not group:
            continue
        tc = TERM_LEGEND_COLOR[term_key]
        legend_html.append(
            f"<div style='margin-top:6px;font-size:0.9em;font-weight:700;color:{tc}'>"
            f"{TERM_LABELS[term_key]}：</div>"
        )
        for ticker, d in group:
            pct = d["market_value"] / total_mv * 100 if total_mv > 0 else 0
            nm = get_name(ticker)
            nm_str = f"{nm} ({ticker})" if nm != ticker else ticker
            legend_html.append(
                f"<div style='padding-left:12px;font-size:0.85em;color:#AAA;line-height:1.7'>"
                f"{nm_str}&nbsp;&nbsp;"
                f"<span style='color:#DDD'>${d['market_value']:,.0f}</span>&nbsp;"
                f"<span style='color:#888'>({pct:.1f}%)</span></div>"
            )
    if cash > 0:
        pct_cash = cash / (total_mv + cash) * 100 if (total_mv + cash) > 0 else 0
        legend_html.append(
            f"<div style='margin-top:6px;font-size:0.9em;font-weight:700;color:#888'>現金：</div>"
            f"<div style='padding-left:12px;font-size:0.85em;color:#AAA;line-height:1.7'>"
            f"現金&nbsp;&nbsp;<span style='color:#DDD'>${cash:,.0f}</span>&nbsp;"
            f"<span style='color:#888'>({pct_cash:.1f}%)</span></div>"
        )
    st.markdown("".join(legend_html), unsafe_allow_html=True)

# ── 損益長條圖────────────────────────────────────────────────────────────────

def _make_bar(labels: list, vals: list, suffix: str) -> go.Figure:
    """水平長條圖 helper，最後一筆為灰色合計列"""
    texts = [f"{v:+.1f}%" if suffix == "%" else f"${v:+,.0f}" for v in vals]
    colors = [COLOR_UP if v >= 0 else COLOR_DOWN for v in vals[:-1]] + ["#AAAAAA"]
    fig = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h",
        marker_color=colors,
        text=texts, textposition="outside", textfont=dict(size=11),
        hovertemplate="%{y}: %{x}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0E1117",
        font=dict(color="#FAFAFA", size=12),
        xaxis=dict(ticksuffix=suffix, gridcolor="#333"),
        yaxis=dict(gridcolor="#333", tickfont=dict(size=12)),
        margin=dict(t=8, b=8, l=8, r=130),
        height=max(220, 40 * (len(labels) + 1)),
    )
    fig.add_vline(x=0, line_color="#555")
    return fig


with chart_col2:
    upnl_pct_total = unrealized / total_cost * 100 if total_cost > 0 else 0.0

    has_realized = bool(realized_by_ticker)
    chart_options = ["未實現損益 %", "未實現損益 $"]
    if has_realized:
        chart_options += ["已實現損益 %", "已實現損益 $"]

    hd_col, toggle_col = st.columns([2, 3])
    with hd_col:
        st.subheader("損益分析")
    with toggle_col:
        chart_view = st.radio("", chart_options,
                              horizontal=True, key="pnl_bar_view",
                              label_visibility="collapsed")

    if chart_view == "未實現損益 %":
        sorted_t = sorted(summary["by_ticker"], key=lambda t: summary["by_ticker"][t]["unrealized_pct"])
        vals   = [summary["by_ticker"][t]["unrealized_pct"] for t in sorted_t] + [upnl_pct_total]
        labels = [get_name(t) for t in sorted_t] + ["─ 合計 ─"]
        suffix = "%"

    elif chart_view == "未實現損益 $":
        sorted_t = sorted(summary["by_ticker"], key=lambda t: summary["by_ticker"][t]["unrealized_pnl"])
        vals   = [summary["by_ticker"][t]["unrealized_pnl"] for t in sorted_t] + [unrealized]
        labels = [get_name(t) for t in sorted_t] + ["─ 合計 ─"]
        suffix = ""

    elif chart_view == "已實現損益 %":
        r_total = sum(realized_by_ticker.values())
        total_buy_all = sum(total_buy_cost_by_ticker.get(t, 1) for t in realized_by_ticker)
        def _rpct(t):
            c = total_buy_cost_by_ticker.get(t, 0)
            return realized_by_ticker[t] / c * 100 if c > 0 else 0.0
        sorted_t = sorted(realized_by_ticker, key=_rpct)
        vals   = [_rpct(t) for t in sorted_t] + [r_total / total_buy_all * 100 if total_buy_all > 0 else 0.0]
        labels = [get_name(t) for t in sorted_t] + ["─ 合計 ─"]
        suffix = "%"

    else:  # 已實現損益 $
        r_total = sum(realized_by_ticker.values())
        sorted_t = sorted(realized_by_ticker, key=lambda t: realized_by_ticker[t])
        vals   = [realized_by_ticker[t] for t in sorted_t] + [r_total]
        labels = [get_name(t) for t in sorted_t] + ["─ 合計 ─"]
        suffix = ""

    st.plotly_chart(_make_bar(labels, vals, suffix),
                    use_container_width=True, config={"displayModeBar": False})

with tab_watch:
    _watch_items_home = _load_watch_items_home(current_user)
    _watch_tickers_home = [item["ticker"] for item in _watch_items_home if item["ticker"]]
    _ticker_to_page_home = {item["ticker"]: item["page_id"] for item in _watch_items_home}

    wa_col, wb_col = st.columns([5, 1])
    with wa_col:
        new_watch = st.text_input(
            "新增代號", placeholder="例：2454.TW 或 AAPL",
            label_visibility="collapsed", key="watch_input_home",
        ).strip().upper()
    with wb_col:
        if st.button("新增", key="watch_add_home", use_container_width=True):
            if not new_watch:
                st.warning("請輸入代號")
            elif new_watch in _watch_tickers_home:
                st.warning(f"{new_watch} 已在清單中")
            else:
                with st.spinner("新增中..."):
                    try:
                        add_to_watchlist(new_watch, current_user)
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"新增失敗：{e}")

    if not _watch_tickers_home:
        st.info("觀察清單為空，請輸入股票代號新增。")
    else:
        with st.spinner("載入觀察清單報價..."):
            watch_data = load_watchlist(tuple(_watch_tickers_home))

        for i in range(0, len(watch_data), 2):
            wcols = st.columns(2)
            for j, d in enumerate(watch_data[i: i + 2]):
                tk = d["ticker"]
                nm = get_name(tk)
                header = (
                    f"{nm} <span style='color:#888;font-size:0.82em'>({tk})</span>"
                    if nm != tk else tk
                )
                with wcols[j]:
                    if not d["ok"]:
                        st.markdown(
                            f"<div style='background:#1C1C2E;border-radius:12px;padding:16px 18px;margin-bottom:4px;'>"
                            f"<div style='font-size:1.05em;font-weight:700;margin-bottom:6px;'>{header}</div>"
                            f"<div style='color:#666'>無法取得報價</div></div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        c = COLOR_UP if d["change"] > 0 else (COLOR_DOWN if d["change"] < 0 else COLOR_NEUTRAL)
                        arrow = pnl_arrow(d["change"])
                        sign = "+" if d["change"] >= 0 else ""
                        st.markdown(
                            f"<div style='background:#1C1C2E;border-radius:12px;padding:16px 18px;margin-bottom:4px;'>"
                            f"<div style='font-size:1.05em;font-weight:700;margin-bottom:6px;'>{header}</div>"
                            f"<div style='font-size:1.4em;font-weight:600;margin-bottom:4px;'>${d['price']:,.2f}</div>"
                            f"<div style='font-size:1em;color:{c};'>"
                            f"{arrow} {sign}{d['change']:,.2f}　({sign}{d['pct']:.2f}%)</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        if st.button("📈 走勢圖", key=f"watch_chart_{tk}", use_container_width=True):
                            st.session_state["chart_ticker"] = tk
                            st.switch_page("pages/1_charts.py")
                    with btn_c2:
                        page_id_home = _ticker_to_page_home.get(tk)
                        if page_id_home and st.button("移除", key=f"home_rm_{tk}", use_container_width=True):
                            with st.spinner(f"移除 {tk}..."):
                                try:
                                    delete_trade(page_id_home)
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"移除失敗：{e}")

st.divider()
st.caption(
    "資料每 5 分鐘自動快取。⚠️ 成本均價含手續費，與券商 APP 顯示的「不含費用均價」可能略有差異。"
)
