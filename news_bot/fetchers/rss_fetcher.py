import calendar
import feedparser
from datetime import datetime, timedelta, timezone
from typing import Optional
from config import RSS_FEEDS, MAX_ARTICLE_CHARS, MAX_SYSTEMIC_NEWS, MACRO_KEYWORDS

TWZ = timezone(timedelta(hours=8))


def _parse_pub_time(entry) -> Optional[datetime]:
    """從 feedparser entry 取出發布時間（只用 published，不用 updated）"""
    t = entry.get("published_parsed")
    if t:
        try:
            return datetime.fromtimestamp(calendar.timegm(t), tz=TWZ)
        except Exception:
            pass
    return None


def _relevance_score(title: str, summary: str) -> int:
    """命中幾個總經/地緣政治關鍵字"""
    text = (title + " " + summary).lower()
    return sum(1 for kw in MACRO_KEYWORDS if kw in text)


def _recency_weight(pub_time: datetime, now: datetime) -> float:
    """越新越高：6h 內 ×3、12h 內 ×2、24h 內 ×1"""
    hours_old = (now - pub_time).total_seconds() / 3600
    if hours_old <= 6:
        return 3.0
    elif hours_old <= 12:
        return 2.0
    else:
        return 1.0


def fetch_rss_news() -> list[dict]:
    """
    只抓「昨天 08:30 至今」的新聞；不夠則自動往前擴（最多 72h）。
    按（關鍵字相關性 × 時效 + 跨媒體熱度）排序，取前 N 篇。
    """
    now = datetime.now(TWZ)
    today_830 = now.replace(hour=8, minute=30, second=0, microsecond=0)

    if now > today_830 and now.weekday() < 5:
        # 今天是工作日且已過 08:30 → 從今天 08:30 開始抓
        cutoff = today_830
    else:
        # 還沒到 08:30、或剛好 08:30、或週末 → 往前找最近的工作日 08:30
        check = now - timedelta(days=1)
        while check.weekday() >= 5:   # 跳過週末
            check -= timedelta(days=1)
        cutoff = check.replace(hour=8, minute=30, second=0, microsecond=0)

    raw: list[dict] = []
    title_hits: dict[str, int] = {}   # 同標題出現在幾個 feed → 跨媒體熱度

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            source_name = feed.feed.get("title", feed_url)

            for entry in feed.entries:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                link = entry.get("link", "")

                if not title:
                    continue

                pub_time = _parse_pub_time(entry)
                if pub_time is None:
                    continue    # 無日期直接跳過

                if len(summary) > MAX_ARTICLE_CHARS:
                    summary = summary[:MAX_ARTICLE_CHARS] + "..."

                relevance = _relevance_score(title, summary)
                recency_w = _recency_weight(pub_time, now)
                score = (relevance + 1) * recency_w

                title_hits[title] = title_hits.get(title, 0) + 1

                raw.append({
                    "title": title,
                    "summary": summary,
                    "source": source_name,
                    "link": link,
                    "_pub_time": pub_time,
                    "_score": score,
                })

        except Exception as e:
            print(f"[RSS] 抓取失敗 {feed_url}: {e}")

    # 跨媒體熱度加分
    for a in raw:
        extra = title_hits.get(a["title"], 1) - 1
        a["_score"] += extra * 0.5

    # 去重：同標題只留分數最高的那篇
    best: dict[str, dict] = {}
    for a in raw:
        t = a["title"]
        if t not in best or a["_score"] > best[t]["_score"]:
            best[t] = a

    all_articles = sorted(best.values(), key=lambda x: (x["_score"], x["_pub_time"]), reverse=True)

    # 時間過濾：從「昨天 8:30」開始，若不夠則每次往前延 24h（最多 72h）
    for extra_days in range(3):
        window_cutoff = cutoff - timedelta(days=extra_days)
        filtered = [a for a in all_articles if a["_pub_time"] >= window_cutoff]
        if len(filtered) >= MAX_SYSTEMIC_NEWS:
            break
    else:
        filtered = all_articles   # 還是不夠就全取

    actual_cutoff = cutoff - timedelta(days=extra_days) if extra_days > 0 else cutoff
    window_label = actual_cutoff.strftime("%m/%d %H:%M")
    if extra_days > 0:
        window_label += f"（往前延 {extra_days} 天）"
    print(f"  找到 {len(filtered)} 篇新聞（{window_label} 後）")

    # 清除內部欄位，保留格式化後的發布時間
    for a in filtered:
        a.pop("_score", None)
        pub = a.pop("_pub_time", None)
        if pub:
            a["pub_time"] = pub.strftime("%m/%d %H:%M")

    news_window = f"{actual_cutoff.strftime('%m/%d %H:%M')} ～ {now.strftime('%m/%d %H:%M')} (台灣時間)"
    return filtered[:MAX_SYSTEMIC_NEWS], news_window
