import yfinance as yf
from config import WATCHLIST, MAX_STOCK_NEWS_PER_TICKER, MAX_ARTICLE_CHARS


def fetch_stock_news() -> list[dict]:
    """
    依 WATCHLIST 抓取個股最新新聞
    回傳: [{"ticker": ..., "title": ..., "summary": ..., "link": ...}]
    """
    results = []

    for ticker in WATCHLIST:
        try:
            stock = yf.Ticker(ticker)
            news_items = stock.news or []

            count = 0
            for item in news_items:
                if count >= MAX_STOCK_NEWS_PER_TICKER:
                    break

                content = item.get("content", {})
                title = content.get("title", "").strip()
                summary = content.get("summary", "").strip()
                link = content.get("canonicalUrl", {}).get("url", "")

                if not title:
                    continue

                if len(summary) > MAX_ARTICLE_CHARS:
                    summary = summary[:MAX_ARTICLE_CHARS] + "..."

                results.append({
                    "ticker": ticker,
                    "title": title,
                    "summary": summary,
                    "link": link,
                })
                count += 1

        except Exception as e:
            print(f"[Stock] 抓取 {ticker} 新聞失敗: {e}")

    return results
