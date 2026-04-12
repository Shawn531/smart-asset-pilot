import requests
import yfinance as yf
from config import MARKET_INDICES

_TAIFEX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://mis.taifex.com.tw/",
    "Content-Type": "application/json",
}

def _fetch_taifex_tx() -> dict:
    """
    從 TAIFEX 取台指期近月合約報價（成交量最大的單月合約）
    """
    r = requests.post(
        "https://mis.taifex.com.tw/futures/api/getQuoteList",
        json={"MarketType": "0", "CommodityID": "TX"},
        headers=_TAIFEX_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    quotes = r.json()["RtData"]["QuoteList"]

    # 只留單月合約（排除價差合約，SymbolID 不含 /）
    # 且有成交量
    candidates = [
        q for q in quotes
        if "/" not in q["SymbolID"]
        and q["CLastPrice"] != "0.00"
        and int(q["CTotalVolume"]) > 0
    ]
    if not candidates:
        raise ValueError("TAIFEX: 無有效台指期報價")

    # 取成交量最大的（近月）
    front = max(candidates, key=lambda q: int(q["CTotalVolume"]))

    price    = float(front["CLastPrice"])
    ref      = float(front["CRefPrice"])
    change   = round(float(front["CDiff"]), 2)
    change_pct = round(float(front["CDiffRate"]), 2)

    return {
        "ticker": front["SymbolID"],
        "price": price,
        "change": change,
        "change_pct": change_pct,
    }


def fetch_market_data() -> dict:
    """
    抓取美股收盤 + 亞股開盤數據
    回傳結構化字典供 AI 摘要使用
    """
    result = {"us": {}, "asia": {}}

    for region, indices in MARKET_INDICES.items():
        for name, ticker in indices.items():
            try:
                # 台指期夜盤走 TAIFEX API
                if ticker == "WTX&":
                    result[region][name] = _fetch_taifex_tx()
                    continue

                data = yf.Ticker(ticker)
                info = data.fast_info

                price = round(info.last_price, 2)
                prev_close = round(info.previous_close, 2)
                change = round(price - prev_close, 2)
                change_pct = round((change / prev_close) * 100, 2)

                result[region][name] = {
                    "ticker": ticker,
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                }
            except Exception as e:
                result[region][name] = {"error": str(e)}

    return result


def format_market_summary(market_data: dict) -> str:
    """將大盤數據格式化成文字，供 Gemini 參考"""
    lines = []

    lines.append("【美股收盤】")
    for name, d in market_data["us"].items():
        if "error" not in d:
            arrow = "▲" if d["change"] >= 0 else "▼"
            lines.append(f"  {name}: {d['price']} {arrow}{abs(d['change_pct'])}%")

    lines.append("【亞股開盤】")
    for name, d in market_data["asia"].items():
        if "error" not in d:
            arrow = "▲" if d["change"] >= 0 else "▼"
            lines.append(f"  {name}: {d['price']} {arrow}{abs(d['change_pct'])}%")

    return "\n".join(lines)
