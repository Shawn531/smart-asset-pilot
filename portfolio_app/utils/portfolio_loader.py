"""
공통 포트폴리오 데이터 로더
app.py와 2_accumulation.py가 같은 캐시를 공유하도록 여기에 정의.
같은 함수를 호출하면 Streamlit은 같은 캐시 항목을 재사용한다.
"""

from __future__ import annotations
import streamlit as st

from utils.notion_loader import fetch_trades
from utils.price_fetcher import get_current_prices
from utils.pnl_calculator import (
    compute_positions, compute_summary, compute_cash,
    compute_all_realized_pnl, compute_realized_pnl_by_ticker,
    compute_total_buy_cost_by_ticker,
)


@st.cache_data(ttl=300)
def load_portfolio(user: str):
    """
    即時價格版投組資料，供總覽頁與資產累積摘要共用。
    回傳值與 app.py 原 load_data() 相同。
    """
    trades = fetch_trades(user)
    positions = compute_positions(trades)
    tickers = list(positions.keys())
    prices = get_current_prices(tickers) if tickers else {}
    summary = compute_summary(positions, prices)
    summary["total_realized_pnl"] = compute_all_realized_pnl(trades)
    cash = compute_cash(trades)
    realized_by_ticker = compute_realized_pnl_by_ticker(trades)
    total_buy_cost_by_ticker = compute_total_buy_cost_by_ticker(trades)
    return trades, positions, prices, summary, cash, realized_by_ticker, total_buy_cost_by_ticker
