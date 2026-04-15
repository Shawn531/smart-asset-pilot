"""
損益計算器
- FIFO 持倉計算
- 未實現 / 已實現損益（含完全平倉股票）
- 資產累積歷史（每日快照）
"""

from __future__ import annotations
import pandas as pd
from datetime import date, datetime, timedelta, timezone
from collections import deque
from dataclasses import dataclass, field


TERM_LABELS = {"long": "長期", "mid": "中期", "short": "短期"}

_TZ_TW = timezone(timedelta(hours=8))


def _today_tw() -> date:
    """回傳台灣時區（UTC+8）的今日日期"""
    return datetime.now(_TZ_TW).date()


@dataclass
class Position:
    ticker: str
    term: str
    shares: float          # 目前持有股數
    cost_basis: float      # 總成本（含手續費）
    first_buy_date: date   # 最舊剩餘批次的買入日期
    realized_pnl: float = 0.0

    @property
    def avg_cost(self) -> float:
        return self.cost_basis / self.shares if self.shares > 0 else 0.0

    @property
    def holding_days(self) -> int:
        # 使用台灣時區今日日期，避免 UTC 誤差
        return (_today_tw() - self.first_buy_date).days


def compute_cash(trades: list[dict]) -> float:
    """
    從交易紀錄動態計算現金餘額：
      入金(deposit) + 賣出收入 - 出金(withdraw) - 買入支出（含手續費）
    """
    cash = 0.0
    for t in trades:
        action = t["action"]
        if action == "deposit":
            cash += t["price"]
        elif action == "withdraw":
            cash -= t["price"]
        elif action == "buy" and t["ticker"] != "CASH":
            cash -= t["shares"] * t["price"] + t["fee"]
        elif action == "sell" and t["ticker"] != "CASH":
            cash += t["shares"] * t["price"] - t["fee"]
    return cash


def _action_sort_key(action: str) -> int:
    """同一天內的排序優先級：buy=0（先處理），sell=1，其他=2"""
    return 0 if action == "buy" else (1 if action == "sell" else 2)


def compute_positions(trades: list[dict]) -> dict[str, Position]:
    """
    用 FIFO 計算當前所有持倉。
    deposit/withdraw 類型會略過（只計算股票持倉）。
    回傳 {ticker: Position}（僅含有持倉的股票）。

    重要：先按日期排序，同一天內買入優先於賣出，
    確保日內沖交易（沖買/沖賣）能正確互相抵消。
    """
    # 同日內 buy 優先於 sell，防止日沖交易排序造成錯誤持倉
    sorted_trades = sorted(
        trades,
        key=lambda t: (t.get("date") or "", _action_sort_key(t.get("action", ""))),
    )

    lots: dict[str, deque] = {}
    realized: dict[str, float] = {}
    term_map: dict[str, str] = {}

    for t in sorted_trades:
        ticker = t["ticker"]
        action = t["action"]
        shares = t["shares"]
        price = t["price"]
        fee = t["fee"]
        trade_date = date.fromisoformat(t["date"]) if t["date"] else _today_tw()
        term = t["term"] or "long"

        if action in ("deposit", "withdraw") or ticker == "CASH":
            continue

        if action == "buy":
            if ticker not in lots:
                lots[ticker] = deque()
                realized[ticker] = 0.0
            # 成本含手續費，攤入每股
            cost_per_share = (shares * price + fee) / shares
            lots[ticker].append({"shares": shares, "cost": cost_per_share, "date": trade_date})
            term_map[ticker] = term

        elif action == "sell":
            if ticker not in lots:
                continue
            sell_price_net = price - fee / shares  # 每股淨售價
            remaining = shares
            while remaining > 0 and lots[ticker]:
                lot = lots[ticker][0]
                if lot["shares"] <= remaining:
                    realized[ticker] += (sell_price_net - lot["cost"]) * lot["shares"]
                    remaining -= lot["shares"]
                    lots[ticker].popleft()
                else:
                    realized[ticker] += (sell_price_net - lot["cost"]) * remaining
                    lot["shares"] -= remaining
                    remaining = 0

    positions: dict[str, Position] = {}
    for ticker, lot_queue in lots.items():
        total_shares = sum(l["shares"] for l in lot_queue)
        if total_shares < 0.001:
            continue
        total_cost = sum(l["shares"] * l["cost"] for l in lot_queue)
        # 最舊剩餘批次日期（FIFO 消化後更準確）
        oldest_lot_date = lot_queue[0]["date"] if lot_queue else _today_tw()
        positions[ticker] = Position(
            ticker=ticker,
            term=term_map.get(ticker, "long"),
            shares=total_shares,
            cost_basis=total_cost,
            first_buy_date=oldest_lot_date,
            realized_pnl=realized.get(ticker, 0.0),
        )

    return positions


def compute_all_realized_pnl(trades: list[dict]) -> float:
    """
    計算所有歷史已實現損益，含完全平倉的股票。
    修正原本 compute_positions 遺漏完全賣光股票的問題。
    使用與 compute_positions 相同的 FIFO 邏輯。
    """
    lots: dict[str, deque] = {}
    total_realized = 0.0

    sorted_trades = sorted(
        trades,
        key=lambda t: (t.get("date") or "", _action_sort_key(t.get("action", ""))),
    )

    for t in sorted_trades:
        ticker = t["ticker"]
        action = t["action"]
        if action in ("deposit", "withdraw") or ticker == "CASH":
            continue

        shares = t["shares"]
        price = t["price"]
        fee = t["fee"]

        if action == "buy":
            if ticker not in lots:
                lots[ticker] = deque()
            cost_per_share = (shares * price + fee) / shares
            lots[ticker].append({"shares": shares, "cost": cost_per_share})

        elif action == "sell" and ticker in lots:
            sell_price_net = price - fee / shares
            remaining = shares
            while remaining > 0 and lots[ticker]:
                lot = lots[ticker][0]
                if lot["shares"] <= remaining:
                    total_realized += (sell_price_net - lot["cost"]) * lot["shares"]
                    remaining -= lot["shares"]
                    lots[ticker].popleft()
                else:
                    total_realized += (sell_price_net - lot["cost"]) * remaining
                    lot["shares"] -= remaining
                    remaining = 0

    return total_realized


def compute_summary(
    positions: dict[str, Position],
    prices: dict[str, float | None],
) -> dict:
    """
    計算投組摘要。
    total_realized_pnl 僅含當前有持倉股票的已實現，
    完整值請用 compute_all_realized_pnl()（在 app.py 中覆蓋）。
    """
    by_term: dict[str, dict] = {
        t: {"market_value": 0.0, "cost": 0.0, "unrealized_pnl": 0.0}
        for t in ["long", "mid", "short"]
    }
    by_ticker: dict[str, dict] = {}
    total_realized = 0.0

    for ticker, pos in positions.items():
        price = prices.get(ticker)
        if price is None:
            continue

        market_value = price * pos.shares
        unrealized = market_value - pos.cost_basis
        unrealized_pct = (unrealized / pos.cost_basis * 100) if pos.cost_basis > 0 else 0.0

        term = pos.term if pos.term in by_term else "long"
        by_term[term]["market_value"] += market_value
        by_term[term]["cost"] += pos.cost_basis
        by_term[term]["unrealized_pnl"] += unrealized
        total_realized += pos.realized_pnl

        by_ticker[ticker] = {
            "term": pos.term,
            "shares": pos.shares,
            "avg_cost": pos.avg_cost,
            "current_price": price,
            "market_value": market_value,
            "cost_basis": pos.cost_basis,       # 總成本（供小卡顯示）
            "unrealized_pnl": unrealized,
            "unrealized_pct": unrealized_pct,
            "realized_pnl": pos.realized_pnl,
            "holding_days": pos.holding_days,
        }

    total_market_value = sum(v["market_value"] for v in by_term.values())
    total_cost = sum(v["cost"] for v in by_term.values())
    total_unrealized = sum(v["unrealized_pnl"] for v in by_term.values())

    return {
        "total_market_value": total_market_value,
        "total_cost": total_cost,
        "total_unrealized_pnl": total_unrealized,
        "total_realized_pnl": total_realized,
        "by_term": by_term,
        "by_ticker": by_ticker,
    }


def compute_accumulation_history(
    trades: list[dict],
    price_histories: dict[str, pd.DataFrame],
    cash_balance: float = 0.0,  # 保留參數以相容舊呼叫，但不使用（從交易動態計算）
) -> pd.DataFrame:
    """
    計算每日資產累積快照，用於 stacked area chart。
    現金從入金/出金/買賣交易動態計算，不依賴靜態 cash_balance 參數。
    回傳 DataFrame，index 為日期，欄位：
        cash, long_value, mid_value, short_value, realized_pnl, total
    """
    if not trades:
        return pd.DataFrame()

    start = date.fromisoformat(trades[0]["date"])
    end = _today_tw()
    date_range = pd.date_range(start=start, end=end, freq="B")  # 工作日

    records = []
    trade_idx = 0
    sorted_trades = sorted(
        trades,
        key=lambda t: (t.get("date") or "", _action_sort_key(t.get("action", ""))),
    )

    lots: dict[str, deque] = {}
    realized: dict[str, float] = {}
    term_map: dict[str, str] = {}
    running_cash = 0.0  # 從交易紀錄動態累積的現金

    for dt in date_range:
        dt_date = dt.date()
        while trade_idx < len(sorted_trades):
            t = sorted_trades[trade_idx]
            t_date = date.fromisoformat(t["date"]) if t["date"] else None
            if t_date is None or t_date > dt_date:
                break

            ticker = t["ticker"]
            action = t["action"]
            shares = t["shares"]
            price = t["price"]
            fee = t["fee"]
            term = t["term"] or "long"

            # 現金流動
            if action == "deposit":
                running_cash += price
            elif action == "withdraw":
                running_cash -= price
            elif action == "buy" and ticker != "CASH":
                running_cash -= shares * price + fee
                if ticker not in lots:
                    lots[ticker] = deque()
                    realized[ticker] = 0.0
                cost_per_share = (shares * price + fee) / shares
                lots[ticker].append({"shares": shares, "cost": cost_per_share})
                term_map[ticker] = term
            elif action == "sell" and ticker != "CASH" and ticker in lots:
                running_cash += shares * price - fee
                sell_price_net = price - fee / shares
                remaining = shares
                while remaining > 0 and lots[ticker]:
                    lot = lots[ticker][0]
                    if lot["shares"] <= remaining:
                        realized[ticker] = realized.get(ticker, 0.0) + (sell_price_net - lot["cost"]) * lot["shares"]
                        remaining -= lot["shares"]
                        lots[ticker].popleft()
                    else:
                        realized[ticker] = realized.get(ticker, 0.0) + (sell_price_net - lot["cost"]) * remaining
                        lot["shares"] -= remaining
                        remaining = 0

            trade_idx += 1

        term_values: dict[str, float] = {"long": 0.0, "mid": 0.0, "short": 0.0}
        for ticker, lot_queue in lots.items():
            total_shares = sum(l["shares"] for l in lot_queue)
            if total_shares <= 0:
                continue
            hist = price_histories.get(ticker)
            if hist is None or hist.empty:
                continue
            available = hist[hist.index <= pd.Timestamp(dt_date)]
            if available.empty:
                continue
            close_raw = available["Close"].iloc[-1]
            if pd.isna(close_raw):
                continue
            close = float(close_raw)
            term = term_map.get(ticker, "long")
            if term in term_values:
                term_values[term] += total_shares * close

        total_realized = sum(realized.values())
        total = running_cash + sum(term_values.values()) + total_realized

        records.append({
            "date": dt_date,
            "cash": running_cash,
            "long_value": term_values["long"],
            "mid_value": term_values["mid"],
            "short_value": term_values["short"],
            "realized_pnl": total_realized,
            "total": total,
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records).set_index("date")
    return df


def compute_realized_pnl_by_ticker(trades: list[dict]) -> dict[str, float]:
    """
    各股已實現損益，含完全平倉的股票。
    回傳 {ticker: realized_pnl}（僅含有已實現損益的股票）。
    """
    lots: dict[str, deque] = {}
    realized: dict[str, float] = {}

    sorted_trades = sorted(
        trades,
        key=lambda t: (t.get("date") or "", _action_sort_key(t.get("action", ""))),
    )

    for t in sorted_trades:
        ticker = t["ticker"]
        action = t["action"]
        if action in ("deposit", "withdraw") or ticker == "CASH":
            continue

        shares = t["shares"]
        price = t["price"]
        fee = t["fee"]

        if action == "buy":
            if ticker not in lots:
                lots[ticker] = deque()
                realized[ticker] = 0.0
            cost_per_share = (shares * price + fee) / shares
            lots[ticker].append({"shares": shares, "cost": cost_per_share})

        elif action == "sell" and ticker in lots:
            sell_price_net = price - fee / shares
            remaining = shares
            while remaining > 0 and lots[ticker]:
                lot = lots[ticker][0]
                if lot["shares"] <= remaining:
                    realized[ticker] = realized.get(ticker, 0.0) + (sell_price_net - lot["cost"]) * lot["shares"]
                    remaining -= lot["shares"]
                    lots[ticker].popleft()
                else:
                    realized[ticker] = realized.get(ticker, 0.0) + (sell_price_net - lot["cost"]) * remaining
                    lot["shares"] -= remaining
                    remaining = 0

    return {t: v for t, v in realized.items() if abs(v) > 0.01}


def compute_total_buy_cost_by_ticker(trades: list[dict]) -> dict[str, float]:
    """各股累計買入總成本（含手續費），用於計算已實現損益率。"""
    cost: dict[str, float] = {}
    for t in trades:
        if t.get("action") == "buy" and t.get("ticker") and t["ticker"] != "CASH":
            ticker = t["ticker"]
            cost[ticker] = cost.get(ticker, 0.0) + t["shares"] * t["price"] + t["fee"]
    return cost
