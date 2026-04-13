# Smart Asset Pilot — 專案狀態

## 專案簡介
每日自動產生金融早報的工具，抓取大盤數據、國際新聞、個股新聞，透過 Gemini AI 整理成結構化中文報告，自動發送到 Telegram。

## 部署狀態
- **GitHub repo**: https://github.com/Shawn531/smart-asset-pilot（私人）
- **自動排程**: GitHub Actions cron `30 0 * * *`（每天 UTC 00:30 = 台灣 08:30）
- **外部觸發**: cron-job.org 每天 08:30 台灣時間打 GitHub repository_dispatch API，確保準時觸發
- **Telegram**: 報告自動發送到個人帳號

## 專案結構
```
smart-asset-pilot/
├── .github/workflows/
│   └── daily_report.yml     # GitHub Actions 排程 + repository_dispatch trigger
├── run_report.bat            # 本地手動執行用（Windows）
└── news_bot/
    ├── main.py              # 主程式（含 Gemini 全失敗時 fallback 到 dry run）
    ├── config.py            # 設定檔
    ├── requirements.txt     # Python 依賴
    ├── .env                 # API keys（不進 git）
    ├── fetchers/
    │   ├── rss_fetcher.py   # RSS 新聞（時間過濾、關鍵字評分、熱度排序）
    │   ├── market_fetcher.py # 大盤數據（yfinance + TAIFEX API 台指夜盤）
    │   └── stock_fetcher.py  # 個股新聞（yfinance）
    ├── ai/
    │   └── summarizer.py    # Gemini AI 摘要（多模型 fallback）
    └── notifiers/
        └── telegram_notifier.py  # Telegram 發送（表格排版、情緒指標）
```

## 技術棧
- Python 3.9（本地 venv 在 `news_bot/venv/`，GitHub Actions 用 3.11）
- `google-genai` — Gemini API
- `yfinance` — 大盤 & 個股數據
- `feedparser` — RSS 解析
- `requests` — TAIFEX API、Telegram Bot API
- `python-dotenv` — 讀取 `.env`

## 設定（config.py）

### WATCHLIST（個股關注清單）
```python
WATCHLIST = ["2330.TW", "2308.TW", "2383.TW", "3715.TW", "NVDA"]
```

### TICKER_NAMES（Telegram 顯示名稱）
```python
TICKER_NAMES = {
    "2330.TW": "台積電",
    "2308.TW": "台達電",
    "2383.TW": "台光電",
    "3715.TW": "定穎投控",
    "NVDA": "NVDA",
}
```

### MARKET_INDICES
- 美股：S&P 500、Nasdaq、Dow Jones、VIX、BRENT（BZ=F）
- 亞股：日經 225、韓國 KOSPI、台指夜盤（TAIFEX API）

### DRY_RUN
- `True` = 跳過 AI，只發送原始新聞清單（測試用）
- `False` = 完整 Gemini 分析 + Telegram 報告（正式使用）

## Gemini 模型 Fallback 順序
1. `gemini-2.5-flash`（主要）
2. `gemini-2.5-flash-lite`（備用，較少過載）
3. `gemini-2.0-flash-001`（最後備用）
4. 全部失敗 → 自動改發 Dry Run 報告

503 時自動等 20 秒重試一次再換下一個模型。

## TAIFEX 台指夜盤
- API: `POST https://mis.taifex.com.tw/futures/api/getQuoteList`
- 同時抓 MarketType `0`（日盤）和 `1`（夜盤）
- 取時間最新的合約（非成交量最大），確保夜盤開市時抓到即時報價
- 夜盤未開時顯示日盤收盤價

## Telegram 報告格式
1. 市場情緒指標（-10 到 +10 進度條）
2. 大盤數據（對齊表格，漲跌幅 🔴/🟢）
3. 大盤總結（Gemini 一段話）
4. 今日重大事件（系統性新聞，附來源連結）
5. 個股動態（顯示公司名稱，附來源連結）

顏色慣例：🔴 偏多（漲）、🟢 偏空（跌）— 台灣市場慣例

## 環境變數（.env）
```
GEMINI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```
GitHub Secrets 也需設定同樣三個變數。

## 執行方式

### 本地執行
```bash
cd news_bot
venv/Scripts/python main.py
```

### 手動觸發 GitHub Actions
GitHub → Actions → Daily Market Report → Run workflow

## 下一步（待討論）
- [ ] 連動「資產紀錄儀表板」（另一個專案）
