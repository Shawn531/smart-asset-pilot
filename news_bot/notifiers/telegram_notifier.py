import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_EXTRA_IDS, TICKER_NAMES

API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def _send(text: str):
    """送出一則 Telegram 訊息給所有接收者（HTML 格式，超過 4096 字自動切分）"""
    all_ids = [TELEGRAM_CHAT_ID] + TELEGRAM_EXTRA_IDS
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chat_id in all_ids:
        for chunk in chunks:
            resp = requests.post(API_URL, json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            if not resp.ok:
                print(f"[Telegram] 發送失敗 ({chat_id}): {resp.text}")


def _market_table(us: dict, asia: dict) -> str:
    """將大盤數據格式化成對齊表格，漲跌幅套用顏色 emoji"""
    rows = ["<pre>"]
    rows.append(f"{'指數':<14}{'價格':>12}  漲跌幅")
    rows.append("─" * 32)

    def row(name, d):
        if "error" in d:
            return
        color = "🔴" if d["change"] >= 0 else "🟢"
        sign  = "+" if d["change"] >= 0 else ""
        pct   = f"{color}{sign}{d['change_pct']}%"
        # CJK 字元佔 2 格，補空白讓欄位對齊
        cjk   = sum(1 for c in name if ord(c) > 0x2E7F)
        pad   = 14 - len(name) - cjk
        rows.append(f"{name}{' ' * pad}{d['price']:>12,.2f}  {pct}")

    for name, d in us.items():
        row(name, d)
    rows.append("─" * 32)
    for name, d in asia.items():
        row(name, d)

    rows.append("</pre>")
    return "\n".join(rows)


def _sentiment_emoji(sentiment: str) -> str:
    return {"多": "🔴", "空": "🟢", "中性": "⚪"}.get(sentiment, "⚪")


def _sentiment_bar(score: int) -> str:
    """將 -10~+10 分數視覺化成進度條，負=紅、正=綠"""
    score = max(-10, min(10, score))
    total = 10
    if score >= 0:
        filled = score
        bar = "⬜" * (total - filled) + "🟥" * filled   # 偏多 → 紅
    else:
        filled = abs(score)
        bar = "🟩" * filled + "⬜" * (total - filled)   # 偏空 → 綠
    return bar


def send_report(report: dict):
    """將完整早報格式化後發到 Telegram"""
    lines = []

    # ── 標題 ──
    lines.append(f"<b>📊 Smart Asset Pilot 每日早報</b>")
    lines.append(f"<i>{report['generated_at']}</i>")
    if report.get("news_window"):
        lines.append(f"<i>📰 新聞時間窗：{report['news_window']}</i>")

    # ── 市場情緒指標 ──
    sentiment = report.get("market_sentiment", {})
    if sentiment:
        score = sentiment.get("score", 0)
        label = sentiment.get("label", "")
        reasoning = sentiment.get("reasoning", "")
        bar = _sentiment_bar(score)
        lines.append("")
        lines.append(f"<b>【市場情緒指標】</b>  {label}")
        lines.append(f"{bar}  <b>{score:+d}/10</b>")
        if reasoning:
            lines.append(f"<i>{reasoning}</i>")

    # ── 大盤數據 ──
    lines.append("")
    lines.append("<b>【大盤數據】</b>")
    us = report["market_data"].get("us", {})
    asia = report["market_data"].get("asia", {})
    lines.append(_market_table(us, asia))

    # ── 大盤總結 ──
    if report.get("market_overview"):
        lines.append("")
        lines.append(f"📝 {report['market_overview']}")

    # ── 系統性事件 ──
    events = report.get("systemic_events", [])
    pub_time_map = report.get("pub_time_map", {})
    if events:
        lines.append("")
        lines.append("<b>【今日重大事件】</b>")
        for i, e in enumerate(events, 1):
            emoji = _sentiment_emoji(e.get("sentiment", ""))
            label = e.get("sentiment", "中性")
            pub = pub_time_map.get(e.get("source_url", ""), "")
            time_tag = f"  <i>{pub}</i>" if pub else ""
            lines.append(f"\n{i}. <b>{e['title']}</b>  {emoji} {label}{time_tag}")
            for pt in e.get("key_points", []):
                lines.append(f"  • {pt}")
            url = e.get("source_url", "")
            if url:
                lines.append(f"  🔗 <a href=\"{url}\">原文連結</a>")

    # ── 個股動態 ──
    stocks = report.get("individual_stocks", [])
    if stocks:
        lines.append("")
        lines.append("<b>【個股動態】</b>")
        for s in stocks:
            emoji = _sentiment_emoji(s.get("sentiment", ""))
            label = s.get("sentiment", "中性")
            ticker = s['ticker']
            display = TICKER_NAMES.get(ticker, ticker)
            lines.append(f"\n<b>{display}</b>  {emoji} {label}")
            for pt in s.get("key_points", []):
                lines.append(f"  • {pt}")
            url = s.get("source_url", "")
            if url:
                lines.append(f"  🔗 <a href=\"{url}\">原文連結</a>")

    _send("\n".join(lines))
    print("[Telegram] 早報已發送")


def send_dry_run_report(report: dict):
    """Dry run 模式：發送原始新聞清單（無 AI 摘要）"""
    lines = []

    lines.append(f"<b>📋 Smart Asset Pilot [DRY RUN]</b>")
    lines.append(f"<i>{report['generated_at']}</i>")

    # 大盤數據
    lines.append("")
    lines.append("<b>【大盤數據】</b>")
    us = report["market_data"].get("us", {})
    asia = report["market_data"].get("asia", {})
    lines.append(_market_table(us, asia))

    # 系統性新聞原始清單
    articles = report.get("systemic_news_raw", [])
    if articles:
        lines.append("")
        lines.append("<b>【今日系統性新聞（原始）】</b>")
        for i, a in enumerate(articles, 1):
            pub = f"  <i>{a['pub_time']}</i>" if a.get("pub_time") else ""
            lines.append(f"\n{i}. <b>{a['title']}</b>{pub}")
            lines.append(f"  來源: {a['source']}")
            if a.get("link"):
                lines.append(f"  🔗 <a href=\"{a['link']}\">原文連結</a>")

    _send("\n".join(lines))
    print("[Telegram] Dry run 報告已發送")
