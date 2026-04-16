"""
股票代號 → 中文名稱對照表
靜態字典找不到時，自動從 yfinance 查詢 shortName 並快取。
"""

from __future__ import annotations

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


# 執行期動態查詢的快取（process 重啟才清空）
_name_cache: dict[str, str] = {}


def get_name(ticker: str) -> str:
    """
    取得股票名稱。
    優先順序：靜態字典 → yfinance shortName → ticker 本身
    查詢結果快取於 _name_cache，避免重複呼叫 API。
    """
    if ticker in TICKER_TO_NAME:
        return TICKER_TO_NAME[ticker]
    if ticker in _name_cache:
        return _name_cache[ticker]
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        name = info.get("shortName") or info.get("longName") or ticker
        _name_cache[ticker] = name
        return name
    except Exception:
        _name_cache[ticker] = ticker
        return ticker
