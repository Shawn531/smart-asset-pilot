"""
損益計算器
- FIFO 持倉計算
- 未實現 / 已實現損益
- 資產累積歷史（每日快照）
"""

from __future__ import annotations
import pandas as pd
from datetime import date, timedelta
from collections import deque
from dataclasses import dataclass, field


TERM_LABELS = {"long": "長期", "mid": "中期", "short": "短期"}


@dataclass
class Position:
    ticker: str
    term: str
    shares: float          # 目前持有股數
    cost_basis: float      # 總成本（含手續費）
    first_buy_date: date   # 第一次買入日期
    realized_pnl: float = 0.0

    @property
    def avg_cost(self) -> float:
        return self.cost_basis / self.shares if self.shares > 0 else 0.0

    @property
    def holding_days(self) -> int:
        return (date.today() - self.first_buy_date).days


def compute_cash(trades: list[dict]) -> float:
    """
    從交易紀錄動態計算現金餘額：
      入金(deposit) + 賣出收入 - 出金(withdraw) - 買入支出
    """
    cash = 0.0
    for t in trades:
        action = t["action"]
        if action == "deposit":
            cash += t["price"]  # 入金：price 欄位存金額
        elif action == "withdraw":
            cash -= t["price"]  # 出金
        elif action == "buy" and t["ticker"] != "CASH":
            cash -= t["shares"] * t["price"] + t["fee"]
        elif action == "sell" and t["ticker"] != "CASH":
            cash += t["shares"] * t["price"] - t["fee"]
    return cash


def compute_positions(trades: list[dict]) -> dict[str, Position]:
    """
    用 FIFO 計算當前所有持倉。
    trades: fetch_trades() 回傳的清單，需已按日期升冪排序。
    deposit/withdraw 類型會略過（只計算股票持倉）。
    回傳 {ticker: Position}（僅含有持倉的股票）。
    """
    lots: dict[str, deque] = {}
    realized: dict[str, float] = {}
    first_buy: dict[str, date] = {}
    term_map: dict[str, str] = {}

    for t in trades:
        ticker = t["ticker"]
        action = t["action"]
        shares = t["shares"]
        price = t["price"]
        fee = t["fee"]
        trade_date = date.fromisoformat(t["date"]) if t["date"] else date.today()
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
            if ticker not in first_buy:
                first_buy[ticker] = trade_date
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

    # 組合成 Position 物件
    positions: dict[str, Position] = {}
    for ticker, lot_queue in lots.items():
        total_shares = sum(l["shares"] for l in lot_queue)
        if total_shares <= 0:
            continue
        total_cost = sum(l["shares"] * l["cost"] for l in lot_queue)
        positions[ticker] = Position(
            ticker=ticker,
            term=term_map.get(ticker, "long"),
            shares=total_shares,
            cost_basis=total_cost,
            first_buy_date=first_buy[ticker],
            realized_pnl=realized.get(ticker, 0.0),
        )

    return positions


def compute_summary(
    positions: dict[str, Position],
    prices: dict[str, float | None],
) -> dict:
    """
    計算投組摘要。
    回傳：
    {
        "total_market_value": float,
        "total_cost": float,
        "total_unrealized_pnl": float,
        "total_realized_pnl": float,
        "by_term": {"long": {...}, "mid": {...}, "short": {...}},
        "by_ticker": {ticker: {...}},
    }
    """
    by_term: dict[str, dict] = {t: {"market_value": 0.0, "cost": 0.0, "unrealized_pnl": 0.0} for t in ["long", "mid", "short"]}
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
    cash_balance: float = 0.0,
) -> pd.DataFrame:
    """
    計算每日資產累積快照，用於 stacked area chart。
    回傳 DataFrame，index 為日期，欄位：
        cash, long_value, mid_value, short_value, realized_pnl, total
    """
    if not trades:
        return pd.DataFrame()

    start = date.fromisoformat(trades[0]["date"])
    end = date.today()
    date_range = pd.date_range(start=start, end=end, freq="B")  # 工作日

    # 預建每日持倉狀態（重播交易）
    records = []
    trade_idx = 0
    sorted_trades = sorted(trades, key=lambda x: x["date"])

    # 用 dict 存各股 lots，和 realized_pnl
    lots: dict[str, deque] = {}
    realized: dict[str, float] = {}
    term_map: dict[str, str] = {}

    for dt in date_range:
        dt_date = dt.date()
        # 套用當日及之前的交易
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

            if action == "buy":
                if ticker not in lots:
                    lots[ticker] = deque()
                    realized[ticker] = 0.0
                cost_per_share = (shares * price + fee) / shares
                lots[ticker].append({"shares": shares, "cost": cost_per_share})
                term_map[ticker] = term

            elif action == "sell":
                if ticker in lots:
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

        # 計算當日各期別市值
        term_values: dict[str, float] = {"long": 0.0, "mid": 0.0, "short": 0.0}
        for ticker, lot_queue in lots.items():
            total_shares = sum(l["shares"] for l in lot_queue)
            if total_shares <= 0:
                continue
            hist = price_histories.get(ticker)
            if hist is None or hist.empty:
                continue
            # 找當日或最近前一個交易日的收盤價
            available = hist[hist.index <= pd.Timestamp(dt_date)]
            if available.empty:
                continue
            close = float(available["Close"].iloc[-1])
            term = term_map.get(ticker, "long")
            if term in term_values:
                term_values[term] += total_shares * close

        total_realized = sum(realized.values())
        total = cash_balance + sum(term_values.values()) + total_realized

        records.append({
            "date": dt_date,
            "cash": cash_balance,
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
