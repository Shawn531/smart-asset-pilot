# Smart Asset Pilot — 專案狀態

## 專案簡介
每日自動產生金融早報的工具，抓取大盤數據、國際新聞、個股新聞，透過 Gemini AI 整理成結構化中文報告，自動發送到 Telegram。

## 部署狀態
- **GitHub repo**: https://github.com/Shawn531/smart-asset-pilot（私人）
- **自動排程**: cron-job.org 每天 08:30 台灣時間打 GitHub repository_dispatch API
- **GitHub Actions**: 收到 dispatch 後執行，也支援手動 Run workflow
- **Telegram**: 報告自動發送到多個帳號

## 專案結構
```
smart-asset-pilot/
├── .github/workflows/
│   └── daily_report.yml     # GitHub Actions（repository_dispatch + workflow_dispatch）
├── run_report.bat            # 本地手動執行用（Windows）
└── news_bot/
    ├── main.py              # 主程式（含 Gemini 全失敗時 fallback 到 dry run）
    ├── config.py            # 設定檔
    ├── requirements.txt     # Python 依賴
    ├── .env                 # API keys（不進 git）
    ├── fetchers/
    │   ├── rss_fetcher.py   # RSS 新聞（台灣時區、時間窗口、關鍵字評分、熱度排序）
    │   ├── market_fetcher.py # 大盤數據（yfinance + TAIFEX API 台指夜盤）
    │   └── stock_fetcher.py  # 個股新聞（yfinance）
    ├── ai/
    │   └── summarizer.py    # Gemini AI 摘要（多模型 fallback）
    └── notifiers/
        └── telegram_notifier.py  # Telegram 發送（表格排版、情緒指標、多人接收）
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

### TELEGRAM_EXTRA_IDS
額外接收早報的 Telegram 帳號清單（直接加 ID 字串即可）：
```python
TELEGRAM_EXTRA_IDS = ["8625444736"]
```

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
- 取時間戳最新的合約，確保夜盤開市時抓到即時報價
- 夜盤未開時顯示日盤收盤價

## 新聞時間窗口邏輯
- 基準時間：台灣時間工作日 08:30
- 今天工作日且已過 08:30 → 今天 08:30 到現在
- 尚未到 08:30 或週末 → 上一個工作日 08:30 到現在
- 週一 08:30 → 上週五 08:30 到現在
- 每篇新聞旁邊顯示發布時間戳

## Telegram 報告格式
1. 市場情緒指標（-10 到 +10 進度條）
2. 大盤數據（對齊表格，漲跌幅 🔴/🟢）
3. 大盤總結（Gemini 一段話）
4. 今日重大事件（標題 + 發布時間 + 來源連結）
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
### 利用 https://console.cron-job.org/jobs 定時觸發
GitHub → Actions → Daily Market Report → Run workflow

## 下一步（待討論）
- [ ] 紀錄一下是怎麼用cron-job排成的
- [ ] 連動「資產紀錄儀表板」（另一個專案）

---

# Portfolio App — 需求 Checklist

### 核心功能
- [x] Streamlit multipage app（總覽 / 走勢圖 / 資產累積 / 新增交易 / 交易紀錄）
- [x] Notion 作為資料庫（notion-client 讀寫）
- [x] FIFO 持倉計算（`pnl_calculator.py`）
- [x] 未實現 / 已實現損益計算（含完全平倉股票）
- [x] 現金餘額從入金/出金/買賣動態計算
- [x] 持股天數用台灣時區（UTC+8）計算
- [x] 同日買賣排序修正（buy 優先於 sell，修正日沖誤算）
- [x] 浮點數極小持倉過濾（< 0.001 股視為平倉）

### 總覽頁（app.py）
- [x] 6 格 Metric cards（總資產、現金、持倉市值、總成本、未實現損益、已實現損益）
- [x] 長/中/短期 Tab 持倉卡片（中文名稱 + 代號、持有天數、成本均價、現價、損益）
- [x] 資產配置圓餅圖（從 12 點逆時針：長期→中期→短期→現金）
- [x] 圓餅圖自訂 HTML 圖例（依期別分組，含現金）
- [x] 短期顏色改為琥珀/橘色（避免與台灣市場紅漲慣例混淆）
- [x] 未實現損益 % ｜ 未實現損益 $ ｜ 已實現損益 % ｜ 已實現損益 $，切換後只顯示對應的一張圖，各自按自己的指標排序。如果還沒有已實現損益，按鈕選項只會出現前兩個。
- [x] Charts 整合進小卡：每張持倉卡片底部加「📈 走勢圖」按鈕，點擊直接跳轉並自動選好該股票

### 走勢圖（1_charts.py）
- [x] K 線蠟燭圖 + 成交量子圖
- [x] MA5 / MA20 / MA60 移動均線
- [x] 買入/賣出標記（金色▲買入、青色▼賣出，與 K 線顏色明顯區分）
- [x] 停損 / 停利水平線
- [x] 報酬率 vs 大盤（^TWII）折線圖
- [x] 觀察清單整合為第二個 Tab（即時報價卡片）
- [x] 可選「當前持倉」或「全部交易過」

### 資產累積（2_accumulation.py）
- [x] Stacked area chart（現金 / 長期 / 中期 / 短期 / 已實現損益）
- [x] 現金從交易紀錄動態計算（非靜態值）
- [ ] 現金出現負值時顯示警告（提示補入金記錄）⏸ 暫時 revert，等確認資料問題後再處理
- [x] 時間範圍切換（全部 / 近1年 / 近6個月 / 近3個月 / 近1個月）
- [x] 合計折線模式

### 新增交易（3_add_trade.py）
- [x] 股票交易 / 現金入出金切換
- [x] 手續費自動估算（台灣 0.1425% × 折扣，最低 $20；賣出加證交稅 0.3%）
- [x] 手續費型別修正（`float()` 避免 StreamlitMixedNumericTypesError）
- [x] 買入/賣出理由必填

### 交易紀錄（4_history.py）
- [x] 月份多選篩選
- [ ] 理由預覽（標題顯示前 18 字）
- [x] 大量刪除模式（全選/取消全選 + 確認）
- [x] 刪除失敗修正（已封存頁面不再報錯）
- [x] 單筆編輯（inline form）

### 效能 / 其他
- [ ] Loading 優化：Notion 暫存計算結果（除非按「重新整理資料」否則讀快取，不重新計算）
- [ ] 放空部位支援（目前 FIFO 僅支援先買後賣）
- [ ] 觀察清單固定清單存入 Notion（目前在 `secrets.toml` 設定）
- [ ] `ticker_names.py` 中文名稱對應表擴充（目前需手動維護）


### USER
- [ ] 加入使用者