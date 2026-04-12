import json
from google import genai
from google.genai import types
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)


def summarize_systemic_news(articles: list[dict], market_summary: str) -> dict:
    """
    將世界重大新聞 + 大盤數據送給 Gemini，回傳結構化中文摘要
    """
    news_text = ""
    for i, a in enumerate(articles, 1):
        news_text += f"\n[{i}] 標題: {a['title']}\n內容: {a['summary']}\n來源: {a['source']}\n連結: {a.get('link', '')}\n"

    prompt = f"""請根據以下資訊生成今日早報。

=== 大盤數據 ===
{market_summary}

=== 國際新聞（英文）===
{news_text}

請輸出以下 JSON 格式（不要加任何其他文字）：
{{
  "market_sentiment": {{
    "score": 整數，範圍 -10（極度偏空）到 +10（極度偏多），0 為中性，根據所有新聞的情緒與衝擊力綜合評估,
    "label": "強烈偏多" 或 "偏多" 或 "中性" 或 "偏空" 或 "強烈偏空",
    "reasoning": "一句話說明判斷依據（約30字）"
  }},
  "market_overview": "一段話總結今日大盤走勢與情緒（約50字）",
  "systemic_events": [
    {{
      "title": "新聞標題（繁體中文翻譯）",
      "key_points": ["重點1", "重點2", "重點3"],
      "sentiment": "多" 或 "空" 或 "中性",
      "impact_score": 整數1到10,
      "source_url": "原始新聞連結（直接複製連結欄位，不要修改）"
    }}
  ]
}}"""

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="你是一位專業的金融分析師助理，負責生成每日金融早報。請務必以繁體中文回覆，並嚴格輸出指定的 JSON 格式，不要加任何其他文字。",
            response_mime_type="application/json",
        )
    )

    text = response.text.strip()

    # 清除可能的 markdown code block
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    return json.loads(text)


def summarize_stock_news(stock_articles: list[dict]) -> list[dict]:
    """
    將個股新聞送給 Gemini，回傳每支股票的結構化摘要
    """
    if not stock_articles:
        return []

    news_text = ""
    for a in stock_articles:
        news_text += f"\n[{a['ticker']}] 標題: {a['title']}\n內容: {a['summary']}\n連結: {a.get('link', '')}\n"

    prompt = f"""請分析以下個股新聞。

=== 個股新聞 ===
{news_text}

請輸出以下 JSON 格式（不要加任何其他文字）：
[
  {{
    "ticker": "股票代碼",
    "key_points": ["重點1", "重點2", "重點3"],
    "sentiment": "多" 或 "空" 或 "中性",
    "impact_score": 整數1到10,
    "source_url": "原始新聞連結（直接複製連結欄位，不要修改）"
  }}
]"""

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="你是一位專業的金融分析師，負責分析個股新聞。請務必以繁體中文回覆，並嚴格輸出指定的 JSON 格式，不要加任何其他文字。",
            response_mime_type="application/json",
        )
    )

    text = response.text.strip()

    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    return json.loads(text)
