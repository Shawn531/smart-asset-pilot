from __future__ import annotations

"""
Notion Database 讀寫工具
讀取交易紀錄、新增、刪除
action 類型：buy | sell | deposit | withdraw
"""

import streamlit as st
from notion_client import Client
from datetime import date


def _get_client() -> Client:
    return Client(auth=st.secrets["NOTION_TOKEN"])


def _get_db_id(user: str | None = None) -> str:
    """
    回傳指定用戶的 Notion Database ID。
    優先查 [USER_DB] 區塊，找不到則 fallback 到 NOTION_DATABASE_ID。
    """
    if user:
        user_db: dict = dict(st.secrets.get("USER_DB", {}))
        if user in user_db:
            return str(user_db[user])
    return st.secrets["NOTION_DATABASE_ID"]


def fetch_trades(user: str | None = None) -> list[dict]:
    """
    從 Notion Database 讀取所有交易紀錄，回傳 list of dict。
    每筆包含 page_id（供刪除使用）。
    action: "buy" | "sell" | "deposit" | "withdraw"
    注意：action="watch" 的觀察清單項目會自動過濾。

    user: 用來決定查哪個 Notion Database（每位用戶獨立 DB）。
    """
    client = _get_client()
    db_id = _get_db_id(user)

    results = []
    cursor = None

    while True:
        kwargs = {
            "database_id": db_id,
            "sorts": [{"property": "date", "direction": "ascending"}],
            "page_size": 100,
        }
        if cursor:
            kwargs["start_cursor"] = cursor

        response = client.databases.query(**kwargs)
        results.extend(response["results"])

        if not response.get("has_more"):
            break
        cursor = response["next_cursor"]

    trades = []
    for page in results:
        props = page["properties"]
        action = _get_select(props, "action")
        if action == "watch":
            continue  # 觀察清單項目，跳過
        trades.append({
            "page_id": page["id"],
            "date": _get_date(props, "date"),
            "ticker": _get_select(props, "ticker"),
            "action": action,
            "term": _get_select(props, "term"),
            "shares": _get_number(props, "shares"),
            "price": _get_number(props, "price"),
            "fee": _get_number(props, "fee"),
            "reason": _get_rich_text(props, "reason"),
            "note": _get_rich_text(props, "note"),
            "name": _get_title(props, "Name"),
        })

    return trades


def fetch_watchlist(user: str | None = None) -> list[dict]:
    """
    從 Notion Database 讀取觀察清單（action="watch"）。
    回傳 list of dict，每筆包含 page_id 與 ticker。
    不使用 server-side filter，以免 "watch" 尚未成為 select option 時拋錯。
    """
    client = _get_client()
    db_id = _get_db_id(user)

    results = []
    cursor = None

    while True:
        kwargs = {"database_id": db_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor

        response = client.databases.query(**kwargs)
        results.extend(response["results"])

        if not response.get("has_more"):
            break
        cursor = response["next_cursor"]

    return [
        {
            "page_id": page["id"],
            "ticker": _get_select(page["properties"], "ticker"),
        }
        for page in results
        if _get_select(page["properties"], "action") == "watch"
    ]


def add_to_watchlist(ticker: str, user: str = "") -> None:
    """
    將股票代號加入觀察清單（在交易 DB 新增 action="watch" 的頁面）。
    """
    from datetime import date as _date
    client = _get_client()
    db_id = _get_db_id(user or None)

    client.pages.create(
        parent={"database_id": db_id},
        properties={
            "Name": {"title": [{"text": {"content": f"觀察 {ticker}"}}]},
            "date": {"date": {"start": _date.today().isoformat()}},
            "ticker": {"select": {"name": ticker}},
            "action": {"select": {"name": "watch"}},
            "term": {"select": {"name": "long"}},
            "shares": {"number": 0},
            "price": {"number": 0},
            "fee": {"number": 0},
            "reason": {"rich_text": [{"text": {"content": ""}}]},
            "note": {"rich_text": [{"text": {"content": ""}}]},
        },
    )


def add_trade(
    ticker: str,
    action: str,
    term: str,
    trade_date: date,
    shares: float,
    price: float,
    fee: float,
    reason: str,
    note: str = "",
    user: str = "",
) -> None:
    """
    新增一筆紀錄到 Notion Database。
    action: "buy" | "sell" | "deposit" | "withdraw"
    現金入金/出金時 ticker="CASH"，shares=1，price=金額
    user: 目前登入的使用者名稱（用於選擇對應的 Notion DB）
    """
    client = _get_client()
    db_id = _get_db_id(user or None)

    action_names = {
        "buy": "買入", "sell": "賣出",
        "deposit": "入金", "withdraw": "出金",
    }
    name = f"{action_names.get(action, action)} {ticker}"

    client.pages.create(
        parent={"database_id": db_id},
        properties={
            "Name": {"title": [{"text": {"content": name}}]},
            "date": {"date": {"start": trade_date.isoformat()}},
            "ticker": {"select": {"name": ticker}},
            "action": {"select": {"name": action}},
            "term": {"select": {"name": term}},
            "shares": {"number": shares},
            "price": {"number": price},
            "fee": {"number": fee},
            "reason": {"rich_text": [{"text": {"content": reason}}]},
            "note": {"rich_text": [{"text": {"content": note}}]},
        },
    )


def delete_trade(page_id: str) -> None:
    """將 Notion 頁面封存（邏輯刪除）。已封存的頁面直接略過。"""
    client = _get_client()
    try:
        client.pages.update(page_id=page_id, archived=True)
    except Exception as e:
        if "archived" in str(e).lower():
            return  # 已刪除，忽略
        raise


def update_trade(
    page_id: str,
    ticker: str,
    action: str,
    term: str,
    trade_date,
    shares: float,
    price: float,
    fee: float,
    reason: str,
    note: str = "",
) -> None:
    """更新一筆交易紀錄的所有欄位"""
    client = _get_client()
    action_names = {
        "buy": "買入", "sell": "賣出",
        "deposit": "入金", "withdraw": "出金",
    }
    name = f"{action_names.get(action, action)} {ticker}"
    client.pages.update(
        page_id=page_id,
        properties={
            "Name": {"title": [{"text": {"content": name}}]},
            "date": {"date": {"start": str(trade_date)}},
            "ticker": {"select": {"name": ticker}},
            "action": {"select": {"name": action}},
            "term": {"select": {"name": term}},
            "shares": {"number": shares},
            "price": {"number": price},
            "fee": {"number": fee},
            "reason": {"rich_text": [{"text": {"content": reason}}]},
            "note": {"rich_text": [{"text": {"content": note}}]},
        },
    )


# ── 欄位取值輔助函數 ─────────────────────────────────────────────────────────

def _get_date(props: dict, key: str) -> str:
    try:
        return props[key]["date"]["start"] or ""
    except (KeyError, TypeError):
        return ""


def _get_select(props: dict, key: str) -> str:
    try:
        return props[key]["select"]["name"] or ""
    except (KeyError, TypeError):
        return ""


def _get_number(props: dict, key: str) -> float:
    try:
        val = props[key]["number"]
        return float(val) if val is not None else 0.0
    except (KeyError, TypeError):
        return 0.0


def _get_rich_text(props: dict, key: str) -> str:
    try:
        texts = props[key]["rich_text"]
        return "".join(t["plain_text"] for t in texts)
    except (KeyError, TypeError):
        return ""


def _get_title(props: dict, key: str) -> str:
    try:
        texts = props[key]["title"]
        return "".join(t["plain_text"] for t in texts)
    except (KeyError, TypeError):
        return ""
