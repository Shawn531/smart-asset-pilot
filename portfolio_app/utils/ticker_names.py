"""
股票代號 → 名稱對照
優先順序：
  1. 靜態字典（最快，已知常用股）
  2. TWSE API（上市台股，中文名稱）
  3. TPEX API（上櫃台股，中文名稱）
  4. yfinance shortName（美股等，英文）
  5. ticker 本身
"""

from __future__ import annotations
import requests

TICKER_TO_NAME: dict[str, str] = {
    # 半導體
    "2330.TW": "台積電",
    "2454.TW": "聯發科",
    "2303.TW": "聯電",
    "3711.TW": "日月光投控",
    "6415.TW": "矽力-KY",
    "2379.TW": "瑞昱",
    "4919.TW": "新唐",
    "3034.TW": "聯詠",
    "4966.TW": "譜瑞-KY",
    "6770.TW": "力積電",
    "5347.TW": "世界先進",
    # 電子零組件
    "2308.TW": "台達電",
    "2317.TW": "鴻海",
    "2382.TW": "廣達",
    "2383.TW": "台光電",
    "2313.TW": "華通",
    "2489.TW": "瑞軒",
    "6239.TW": "力成",
    "3037.TW": "欣興",
    "3189.TW": "景碩",
    "8046.TW": "南電",
    "2367.TW": "燿華",
    # 面板
    "3481.TW": "群創",
    "2409.TW": "友達",
    # 記憶體/儲存
    "2337.TW": "旺宏",
    "2344.TW": "華邦電",
    # 網通/IC設計
    "6416.TW": "位速",
    "3592.TW": "瑞鼎",
    # 傳產/其他
    "6196.TW": "福懋科",
    "3715.TW": "定穎投控",
    "4528.TW": "大魯閣",
    # ETF
    "0050.TW": "元大台灣50",
    "0056.TW": "元大高股息",
    "00878.TW": "國泰永續高股息",
    "006208.TW": "富邦台50",
    "00850.TW": "元大台灣ESG永續",
    # 美股
    "NVDA": "NVDA",
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "TSLA": "TSLA",
}

# ── 動態快取 ──────────────────────────────────────────────────────────────────
_twse_names: dict[str, str] = {}   # code (不含 .TW) → 中文名
_tpex_names: dict[str, str] = {}   # code (不含 .TWO) → 中文名
_yf_cache: dict[str, str] = {}     # ticker → 英文名
_twse_fetched = False
_tpex_fetched = False


def _load_twse() -> dict[str, str]:
    """從 TWSE OpenAPI 載入所有上市股票中文名稱（只跑一次）"""
    global _twse_names, _twse_fetched
    if _twse_fetched:
        return _twse_names
    _twse_fetched = True
    try:
        resp = requests.get(
            "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
            timeout=10,
        )
        for item in resp.json():
            code = item.get("Code", "")
            name = item.get("Name", "")
            if code and name:
                _twse_names[code] = name
    except Exception:
        pass
    return _twse_names


def _load_tpex() -> dict[str, str]:
    """從 TPEX OpenAPI 載入所有上櫃股票中文名稱（只跑一次）"""
    global _tpex_names, _tpex_fetched
    if _tpex_fetched:
        return _tpex_names
    _tpex_fetched = True
    try:
        resp = requests.get(
            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
            timeout=10,
        )
        for item in resp.json():
            code = item.get("SecuritiesCompanyCode", "")
            name = item.get("CompanyName", "")
            if code and name:
                _tpex_names[code] = name
    except Exception:
        pass
    return _tpex_names


def get_name(ticker: str) -> str:
    """
    取得股票名稱（盡量回傳中文）。
    1. 靜態字典
    2. TWSE API（.TW 上市股）
    3. TPEX API（.TWO 上櫃股）
    4. yfinance shortName（美股）
    5. ticker 本身
    """
    # 1. 靜態字典
    if ticker in TICKER_TO_NAME:
        return TICKER_TO_NAME[ticker]

    # 2. 台股上市（.TW）
    if ticker.endswith(".TW"):
        code = ticker[:-3]
        names = _load_twse()
        if code in names:
            return names[code]

    # 3. 台股上櫃（.TWO）
    if ticker.endswith(".TWO"):
        code = ticker[:-4]
        names = _load_tpex()
        if code in names:
            return names[code]

    # 4. yfinance（美股等）
    if ticker in _yf_cache:
        return _yf_cache[ticker]
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        name = info.get("shortName") or info.get("longName") or ticker
        _yf_cache[ticker] = name
        return name
    except Exception:
        _yf_cache[ticker] = ticker
        return ticker
