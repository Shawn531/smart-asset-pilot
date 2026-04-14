from __future__ import annotations

"""
yfinance 價格工具
- 即時報價（fast_info）
- 歷史 OHLC（history()）
台股用 .TW 後綴，大盤用 ^TWII
"""

import yfinance as yf
import pandas as pd
from datetime import date


def get_current_price(ticker: str) -> float | None:
    """
    取得即時（或最近）收盤價。
    失敗回傳 None。
    """
    try:
        info = yf.Ticker(ticker).fast_info
        price = info.last_price
        if price is None or price != price:  # NaN check
            return None
        return round(float(price), 2)
    except Exception:
        return None


def get_current_prices(tickers: list[str]) -> dict[str, float | None]:
    """批次取得多支股票即時價格，回傳 {ticker: price}"""
    return {t: get_current_price(t) for t in tickers}


def get_history(
    ticker: str,
    start: date | str,
    end: date | str | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    取得歷史 OHLCV 資料。
    回傳 DataFrame，index 為 DatetimeIndex，欄位含 Open/High/Low/Close/Volume。
    失敗回傳空 DataFrame。
    """
    try:
        df = yf.Ticker(ticker).history(
            start=str(start),
            end=str(end) if end else None,
            interval=interval,
            auto_adjust=True,
        )
        if df.empty:
            return pd.DataFrame()
        df.index = df.index.tz_localize(None)  # 移除 timezone，統一用 naive datetime
        return df
    except Exception:
        return pd.DataFrame()


def get_multi_history(
    tickers: list[str],
    start: date | str,
    end: date | str | None = None,
) -> dict[str, pd.DataFrame]:
    """
    批次取得多支股票的歷史收盤價，回傳 {ticker: DataFrame}。
    用於資產累積計算。
    """
    return {t: get_history(t, start, end) for t in tickers}


def get_close_on_date(ticker: str, target_date: date) -> float | None:
    """
    取得特定日期的收盤價（用於 P&L 歷史計算）。
    若當天無交易（假日），取最近的前一個交易日。
    """
    try:
        df = get_history(ticker, start=target_date, end=None)
        if df.empty:
            return None
        # 取最近一筆
        return round(float(df["Close"].iloc[-1]), 2)
    except Exception:
        return None
