import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Telegram 通知
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_EXTRA_IDS = ["8625444736"]  # 額外接收早報的帳號

# 個股關注清單（未來將與資產管理模組連動）
WATCHLIST = [
    "2330.TW",  # 台積電
    "2308.TW",
    "2383.TW",
    "3715.TW",
    "NVDA",
]

TICKER_NAMES = {
    "2330.TW": "台積電",
    "2308.TW": "台達電",
    "2383.TW": "台光電",
    "3715.TW": "定穎投控",
    "NVDA": "NVDA",
}

# 大盤指數
MARKET_INDICES = {
    "us": {
        "S&P 500": "^GSPC",
        "Nasdaq":  "^IXIC",
        "Dow Jones": "^DJI",
        "VIX": "^VIX",
        "BRENT": "BZ=F"
    },
    "asia": {
        "日經 225": "^N225",
        "韓國 KOSPI": "^KS11",
        "台指夜盤": "WTX&"
    }
}

# RSS 新聞來源（聚焦總經、地緣政治、政策）
RSS_FEEDS = [
    "https://finance.yahoo.com/news/rssindex",                  # Yahoo Finance（即時，49篇）
    "http://feeds.marketwatch.com/marketwatch/topstories/",     # MarketWatch 即時
    "https://feeds.bloomberg.com/markets/news.rss",             # Bloomberg Markets
    "https://www.investing.com/rss/news.rss",                   # Investing.com
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",   # CNBC Latest News
    "https://www.cnbc.com/id/15839069/device/rss/rss.html",    # CNBC US Markets
    "https://www.cnbc.com/id/20910258/device/rss/rss.html",    # CNBC Economy
]

# 系統性新聞關鍵字權重（命中越多、排越前面送給 AI）
MACRO_KEYWORDS = [
    # 聯準會 / 貨幣政策
    "fed", "federal reserve", "fomc", "interest rate", "rate cut", "rate hike",
    "powell", "inflation", "cpi", "gdp", "recession", "unemployment",
    # 川普 / 貿易政策
    "trump", "tariff", "trade war", "trade deal", "sanction",
    # 地緣政治
    "war", "military", "missile", "nato", "iran", "russia", "north korea",
    "china", "taiwan", "middle east", "israel", "ukraine",
    # 財政 / 市場
    "treasury", "bond", "yield", "dollar", "debt ceiling",
    "opec", "oil", "energy", "commodity",
]

# 每篇新聞最多取幾字元送給 AI（避免 token 爆炸）
MAX_ARTICLE_CHARS = 1500

# 系統性新聞最多處理幾篇
MAX_SYSTEMIC_NEWS = 5

# 個股新聞每支股票最多幾篇
MAX_STOCK_NEWS_PER_TICKER = 2

# Dry run 模式：True = 跳過 AI 呼叫，只印出抓到的原始新聞清單（用於測試 fetcher）
DRY_RUN = False
