"""
對帳單批次匯入
支援國泰證券 CSV 格式
自動解析 → 預覽 → 一鍵匯入 Notion
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import io
from datetime import date, datetime

from utils.notion_loader import add_trade

st.set_page_config(page_title="對帳單匯入", page_icon="📂", layout="wide")

st.markdown("""
<style>
html, body, [class*="css"] { font-size: 16px; }
</style>
""", unsafe_allow_html=True)

st.title("📂 對帳單批次匯入")
st.caption("支援國泰證券 CSV 對帳單。上傳後預覽，確認後一鍵寫入 Notion。")

# ── 股名 → Yahoo Finance 代號對照表 ───────────────────────────────────────────
NAME_TO_TICKER: dict[str, str] = {
    # 半導體
    "台積電": "2330.TW", "聯發科": "2454.TW", "聯電": "2303.TW",
    "日月光投控": "3711.TW", "矽力-KY": "6415.TW", "瑞昱": "2379.TW",
    "新唐": "4919.TW", "聯詠": "3034.TW", "譜瑞-KY": "4966.TW",
    "力積電": "6770.TW", "世界先進": "5347.TW",
    # 電子零組件
    "台達電": "2308.TW", "鴻海": "2317.TW", "廣達": "2382.TW",
    "台光電": "2383.TW", "華通": "2313.TW", "瑞軒": "2489.TW",
    "力成": "6239.TW", "欣興": "3037.TW", "景碩": "3189.TW",
    "南電": "8046.TW", "燿華": "2367.TW",
    # 面板
    "群創": "3481.TW", "友達": "2409.TW",
    # 記憶體/儲存
    "旺宏": "2337.TW", "華邦電": "2344.TW",
    # 網通/IC設計
    "位速": "6416.TW", "瑞鼎": "3592.TW",
    # 傳產/其他
    "福懋科": "6196.TW", "定穎投控": "3715.TW", "大魯閣": "4528.TW",
    # ETF
    "元大台灣50": "0050.TW", "元大高股息": "0056.TW",
    "國泰永續高股息": "00878.TW", "富邦台50": "006208.TW",
    "元大台灣ESG永續": "00850.TW",
    # 美股（若有）
    "NVDA": "NVDA", "AAPL": "AAPL", "MSFT": "MSFT", "TSLA": "TSLA",
}

ACTION_MAP = {
    "現買": "buy", "現賣": "sell",
    "沖買": "buy", "沖賣": "sell",
}

TERM_OPTIONS = {"長期": "long", "中期": "mid", "短期": "short"}


def clean_number(val) -> float:
    """處理帶引號和逗號的數字字串"""
    try:
        return float(str(val).replace(",", "").replace('"', "").strip())
    except (ValueError, TypeError):
        return 0.0


def parse_statement(content: bytes) -> pd.DataFrame:
    """解析國泰證券 CSV，跳過第一行摘要"""
    text = content.decode("utf-8-sig", errors="replace")
    lines = text.strip().splitlines()
    # 第一行是摘要說明，第二行才是 header
    data_text = "\n".join(lines[1:])
    df = pd.read_csv(io.StringIO(data_text), dtype=str)
    df.columns = df.columns.str.strip()

    df["股數"] = df["成交股數"].apply(clean_number)
    df["成交價_num"] = df["成交價"].apply(clean_number)
    df["手續費_num"] = df["手續費"].apply(clean_number)
    df["交易稅_num"] = df["交易稅"].apply(clean_number).fillna(0)
    df["日期_dt"] = pd.to_datetime(df["日期"], format="%Y/%m/%d").dt.date
    df["action"] = df["買賣別"].map(ACTION_MAP).fillna("buy")
    df["is_daytrade"] = df["買賣別"].str.startswith("沖")
    df["ticker"] = df["股名"].map(NAME_TO_TICKER).fillna("")
    # 手續費含交易稅
    df["total_fee"] = df["手續費_num"] + df["交易稅_num"]

    return df


# ── 上傳 CSV ──────────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "上傳對帳單 CSV（國泰證券格式）",
    type=["csv"],
    help="從國泰證券 App 下載 CSV 後上傳",
)

if not uploaded:
    st.info("請上傳對帳單 CSV 檔案")
    st.stop()

try:
    df = parse_statement(uploaded.read())
except Exception as e:
    st.error(f"解析失敗：{e}")
    st.stop()

st.success(f"成功解析 {len(df)} 筆交易")

# ── 未對應股票提示 ────────────────────────────────────────────────────────────
unmapped = df[df["ticker"] == ""]["股名"].unique().tolist()
if unmapped:
    st.warning(f"以下股票未找到對應代號，請在下方手動填入：{', '.join(unmapped)}")
    for name in unmapped:
        ticker_input = st.text_input(
            f"{name} 的股票代號（例：2330.TW）",
            key=f"manual_{name}",
        ).strip().upper()
        if ticker_input:
            df.loc[df["股名"] == name, "ticker"] = ticker_input

# ── 每支股票設定期別 ──────────────────────────────────────────────────────────
st.divider()
st.subheader("設定各股期別")
st.caption("日沖交易預設為短期，其他預設為中期。可依需求調整。")

all_stocks = df["股名"].unique().tolist()
stock_term: dict[str, str] = {}

cols = st.columns(3)
for i, name in enumerate(all_stocks):
    is_daytrade = df[df["股名"] == name]["is_daytrade"].all()
    default = "短期" if is_daytrade else "長期"
    with cols[i % 3]:
        label = st.selectbox(
            name,
            list(TERM_OPTIONS.keys()),
            index=list(TERM_OPTIONS.keys()).index(default),
            key=f"term_{name}",
        )
        stock_term[name] = TERM_OPTIONS[label]

# ── 預覽表格 ──────────────────────────────────────────────────────────────────
st.divider()
st.subheader("預覽交易紀錄")

df["期別"] = df["股名"].map(lambda n: {"long": "長期", "mid": "中期", "short": "短期"}[stock_term.get(n, "mid")])
df["操作"] = df["買賣別"]

preview = df[["日期", "股名", "ticker", "操作", "期別", "股數", "成交價_num", "total_fee"]].copy()
preview.columns = ["日期", "股名", "代號", "操作", "期別", "股數", "成交價", "手續費+稅"]
preview["成交價"] = preview["成交價"].apply(lambda x: f"${x:,.2f}")
preview["手續費+稅"] = preview["手續費+稅"].apply(lambda x: f"${x:,.0f}")

st.dataframe(preview, use_container_width=True, hide_index=True)

# 統計
buy_count = (df["action"] == "buy").sum()
sell_count = (df["action"] == "sell").sum()
no_ticker = (df["ticker"] == "").sum()
st.caption(f"買入 {buy_count} 筆 ｜ 賣出 {sell_count} 筆 ｜ 代號未填 {no_ticker} 筆")

if no_ticker > 0:
    st.warning("仍有交易未填入股票代號，匯入時將略過這些筆。")

# ── 匯入按鈕 ──────────────────────────────────────────────────────────────────
st.divider()

if "import_done" not in st.session_state:
    st.session_state.import_done = False

if not st.session_state.import_done:
    if st.button("🚀 全部匯入 Notion", type="primary", use_container_width=True):
        to_import = df[df["ticker"] != ""]
        progress = st.progress(0)
        success_count = 0
        fail_count = 0

        for i, (_, row) in enumerate(to_import.iterrows()):
            try:
                add_trade(
                    ticker=row["ticker"],
                    action=row["action"],
                    term=stock_term.get(row["股名"], "long"),
                    trade_date=row["日期_dt"],
                    shares=row["股數"],
                    price=row["成交價_num"],
                    fee=row["total_fee"],
                    reason="對帳單匯入",
                    note=f"委託書號：{row.get('委託書號', '')}",
                )
                success_count += 1
            except Exception:
                fail_count += 1
            progress.progress((i + 1) / len(to_import))

        st.session_state.import_done = True
        st.cache_data.clear()

        if fail_count == 0:
            st.success(f"✅ 成功匯入 {success_count} 筆交易！")
        else:
            st.warning(f"完成：成功 {success_count} 筆，失敗 {fail_count} 筆")
else:
    st.success("✅ 已匯入完成！如需重新匯入，請重新上傳檔案。")
    if st.button("重新上傳"):
        st.session_state.import_done = False
        st.rerun()
