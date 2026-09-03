"""שליפת נתוני מחיר מ-yfinance עבור שלוש מסגרות הזמן: יומי, 4 שעות (מ-60m), שבועי.

תוקן ב-2026-09-03: נמצא שסריקה של 49 טיקרים ברצף מהיר גורמת ל-Yahoo Finance
לחסום/להחזיר תשובות ריקות לחלק ניכר מהבקשות (עד 35/49 בסריקה אחת בפועל
מהלוגים). נוסף retry עם backoff לכל בקשה, ועיכוב קטן בין טיקרים ב-main.py.
"""
from __future__ import annotations

import random
import time

import pandas as pd
import yfinance as yf


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    return df


def _with_retry(fn, tries: int = 3, base_delay: float = 3.0):
    last_exc = None
    for attempt in range(tries):
        try:
            df = fn()
            if df is not None and not df.empty:
                return df
            last_exc = RuntimeError("נתונים ריקים מ-yfinance (כנראה rate-limit)")
        except Exception as e:
            last_exc = e
        if attempt < tries - 1:
            time.sleep(base_delay * (2 ** attempt) + random.uniform(0, 1))
    raise last_exc if last_exc else RuntimeError("שליפת נתונים נכשלה")


def fetch_daily(ticker: str, period: str = "2y") -> pd.DataFrame:
    df = _with_retry(lambda: yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True))
    return _clean(df)


def fetch_weekly(ticker: str) -> pd.DataFrame:
    df = _with_retry(lambda: yf.Ticker(ticker).history(period="5y", interval="1wk", auto_adjust=True))
    return _clean(df)


def fetch_4h(ticker: str) -> pd.DataFrame:
    """yfinance אין לו interval='4h' ישיר - שולפים 60m ומאגדים ל-4 שעות."""
    hourly = _with_retry(lambda: yf.Ticker(ticker).history(period="60d", interval="60m", auto_adjust=True))
    hourly = _clean(hourly)
    if hourly.empty:
        return hourly
    agg = hourly.resample("4h", origin="start_day").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    )
    agg = agg.dropna(subset=["Open", "High", "Low", "Close"])
    return agg


def fetch_all_timeframes(ticker: str) -> dict:
    return {
        "daily": fetch_daily(ticker),
        "4h": fetch_4h(ticker),
        "weekly": fetch_weekly(ticker),
    }
