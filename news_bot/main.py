import json
import os
from datetime import datetime, timezone, timedelta

from fetchers.rss_fetcher import fetch_rss_news
from fetchers.market_fetcher import fetch_market_data, format_market_summary
from fetchers.stock_fetcher import fetch_stock_news
from config import DRY_RUN


def run_daily_report():
    TWZ = timezone(timedelta(hours=8))
    today = datetime.now(TWZ).strftime("%Y-%m-%d %H:%M")
    mode_label = " [DRY RUN]" if DRY_RUN else ""
    print(f"\n{'='*50}")
    print(f"  Smart Asset Pilot 每日早報 — {today}{mode_label}")
    print(f"{'='*50}\n")

    # 1. 抓大盤數據
    print("[1/4] 抓取大盤數據...")
    market_data = fetch_market_data()
    market_summary = format_market_summary(market_data)
    print(market_summary)

    # 2. 抓 RSS 世界新聞
    print("\n[2/4] 抓取世界重大新聞...")
    rss_articles = fetch_rss_news()

    # 3. 抓個股新聞
    print("\n[3/4] 抓取個股新聞...")
    stock_articles = fetch_stock_news()
    print(f"  取得 {len(stock_articles)} 篇個股新聞")

    if DRY_RUN:
        # Dry run：跳過 AI，直接輸出原始新聞清單
        report = {
            "generated_at": today,
            "dry_run": True,
            "market_data": market_data,
            "systemic_news_raw": rss_articles,
            "stock_news_raw": stock_articles,
        }

        print("\n" + "="*50)
        print("  [DRY RUN] 原始新聞清單")
        print("="*50)
        for i, a in enumerate(rss_articles, 1):
            print(f"\n[{i}] {a['title']}")
            print(f"    來源: {a['source']}")
            print(f"    連結: {a['link']}")

        os.makedirs("output", exist_ok=True)
        filename = f"output/dryrun_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n報告已儲存至: {filename}")

        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            from notifiers.telegram_notifier import send_dry_run_report
            send_dry_run_report(report)
        return

    # 4. AI 摘要
    from ai.summarizer import summarize_systemic_news, summarize_stock_news
    print("\n[4/4] 送 Gemini 分析中...")
    systemic_result = summarize_systemic_news(rss_articles, market_summary)
    stock_result = summarize_stock_news(stock_articles)

    # 組合最終報告
    report = {
        "generated_at": today,
        "market_data": market_data,
        "market_sentiment": systemic_result.get("market_sentiment", {}),
        "market_overview": systemic_result.get("market_overview", ""),
        "systemic_events": systemic_result.get("systemic_events", []),
        "individual_stocks": stock_result,
    }

    # 輸出報告
    print("\n" + "="*50)
    print("  AI 摘要結果")
    print("="*50)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # 儲存到檔案
    os.makedirs("output", exist_ok=True)
    filename = f"output/report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n報告已儲存至: {filename}")

    # 發送 Telegram 通知
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        from notifiers.telegram_notifier import send_report
        send_report(report)
    else:
        print("[Telegram] 未設定 token/chat ID，略過發送")

    return report


if __name__ == "__main__":
    run_daily_report()
