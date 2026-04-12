# Smart Asset Pilot — 專案狀態

## 專案簡介
每日自動產生金融早報的工具，抓取大盤數據、國際新聞、個股新聞，透過 Gemini AI 整理成結構化中文報告。

## 目前進度
`news_bot` 模組已完整建立，核心功能完成。

## 專案結構
```
smart-asset-pilot/
└── news_bot/
    ├── main.py              # 主程式，執行後輸出報告到 output/
    ├── config.py            # API key、WATCHLIST、RSS feeds、大盤指數設定
    ├── .env                 # GEMINI_API_KEY（不進 git）
    ├── fetchers/
    │   ├── rss_fetcher.py   # 從 RSS 抓世界重大新聞（Reuters、CNBC）
    │   ├── market_fetcher.py # yfinance 抓大盤（S&P500、Nasdaq、DJI、VIX、日經、KOSPI）
    │   └── stock_fetcher.py  # yfinance 抓個股新聞
    └── ai/
        └── summarizer.py    # Gemini 1.5 Flash 做 AI 摘要（系統性新聞 + 個股）
```

## 技術棧
- Python（venv 在 `news_bot/venv/`）
- `yfinance` — 大盤 & 個股數據
- `feedparser` — RSS 解析
- `anthropic` — Claude Opus 4.6 API
- `python-dotenv` — 讀取 `.env`

## WATCHLIST（個股關注清單）
AAPL, NVDA, TSLA, 2330.TW（台積電）

## 執行方式
```bash
cd news_bot
python main.py
```
輸出報告存至 `news_bot/output/report_YYYYMMDD_HHMM.json`

## 下一步（待討論）
- [ ] 尚未確認
