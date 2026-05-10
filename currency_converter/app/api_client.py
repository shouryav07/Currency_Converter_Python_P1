"""
api_client.py – Fetches live exchange rates and historical OHLC data.

Design decisions
────────────────
• ExchangeRate-API  → live spot rates (free tier supports 1 500 req/month).
• yfinance          → historical daily OHLC for the trend chart (no key needed).
• SQLite            → offline cache so the app still works without internet.
• All network calls run in background threads; callbacks receive results.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import requests
import yfinance as yf
import pandas as pd
from dotenv import load_dotenv

from app.utils import ticker_symbol, date_range, TIMEFRAME_DAYS

# ── Load .env from project root (two levels up from this file) ──────────────
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY", "")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

CACHE_DB   = Path(__file__).resolve().parent.parent / "cache.db"
RATE_TTL   = 3600        # seconds before a cached rate is considered stale (1 hour)
HIST_TTL   = 86_400      # historical data refreshed once per day


# ──────────────────────────────────────────────────────────────────
#  SQLite cache layer
# ──────────────────────────────────────────────────────────────────

def _init_db() -> sqlite3.Connection:
    """Create tables if they don't exist and return a connection."""
    conn = sqlite3.connect(str(CACHE_DB), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rates (
            base        TEXT NOT NULL,
            target      TEXT NOT NULL,
            rate        REAL NOT NULL,
            fetched_at  INTEGER NOT NULL,
            PRIMARY KEY (base, target)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS history (
            symbol      TEXT NOT NULL,
            date        TEXT NOT NULL,
            open        REAL,
            high        REAL,
            low         REAL,
            close       REAL,
            fetched_at  INTEGER NOT NULL,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS full_rate_snapshot (
            base        TEXT PRIMARY KEY,
            payload     TEXT NOT NULL,
            fetched_at  INTEGER NOT NULL
        )
    """)
    conn.commit()
    return conn


# Global DB connection (thread-safe with check_same_thread=False + a lock)
_db_lock = threading.Lock()
_conn    = _init_db()


def _db_get_rate(base: str, target: str) -> Optional[tuple[float, int]]:
    """Return (rate, fetched_at) from cache or None if absent / stale."""
    with _db_lock:
        cur = _conn.execute(
            "SELECT rate, fetched_at FROM rates WHERE base=? AND target=?",
            (base, target),
        )
        row = cur.fetchone()
    return (row[0], row[1]) if row else None


def _db_set_rate(base: str, target: str, rate: float) -> None:
    with _db_lock:
        _conn.execute(
            "INSERT OR REPLACE INTO rates (base, target, rate, fetched_at) VALUES (?,?,?,?)",
            (base, target, rate, int(time.time())),
        )
        _conn.commit()


def _db_get_snapshot(base: str) -> Optional[dict]:
    """Return full rates dict from snapshot cache."""
    with _db_lock:
        cur = _conn.execute(
            "SELECT payload, fetched_at FROM full_rate_snapshot WHERE base=?",
            (base,),
        )
        row = cur.fetchone()
    if not row:
        return None
    age = time.time() - row[1]
    if age > RATE_TTL:
        return None
    return json.loads(row[0])


def _db_set_snapshot(base: str, rates: dict) -> None:
    with _db_lock:
        _conn.execute(
            "INSERT OR REPLACE INTO full_rate_snapshot (base, payload, fetched_at) VALUES (?,?,?)",
            (base, json.dumps(rates), int(time.time())),
        )
        _conn.commit()


def _db_get_history(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Load cached OHLC rows for the symbol covering the last `days`."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    with _db_lock:
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close, fetched_at "
            "FROM history WHERE symbol=? AND date>=? ORDER BY date",
            _conn,
            params=(symbol, cutoff),
        )
    if df.empty:
        return None
    # Only return cached data if freshly fetched (within HIST_TTL)
    latest_fetch = df["fetched_at"].max()
    if time.time() - latest_fetch > HIST_TTL:
        return None
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "open", "high", "low", "close"]]


def _db_set_history(symbol: str, df: pd.DataFrame) -> None:
    now = int(time.time())
    rows = [
        (symbol, str(row.date)[:10], row.open, row.high, row.low, row.close, now)
        for row in df.itertuples()
    ]
    with _db_lock:
        _conn.executemany(
            "INSERT OR REPLACE INTO history "
            "(symbol, date, open, high, low, close, fetched_at) VALUES (?,?,?,?,?,?,?)",
            rows,
        )
        _conn.commit()


# ──────────────────────────────────────────────────────────────────
#  Live rate fetching
# ──────────────────────────────────────────────────────────────────

def fetch_all_rates(base: str) -> Optional[dict[str, float]]:
    """
    Fetch all rates for `base` currency from ExchangeRate-API.
    Falls back to cached snapshot if the network call fails.
    Returns dict like {'EUR': 0.92, 'GBP': 0.79, …} or None on total failure.
    """
    # 1. Try live API
    if EXCHANGE_RATE_API_KEY:
        url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/{base}"
    else:
        # Free public endpoint (no key, limited pairs) – fallback
        url = f"https://open.er-api.com/v6/latest/{base}"

    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        rates: dict = data.get("conversion_rates") or data.get("rates", {})
        if rates:
            _db_set_snapshot(base, rates)
            return rates
    except Exception as exc:
        print(f"[api_client] live rate fetch failed: {exc}")

    # 2. Fall back to DB snapshot (possibly stale, still useful)
    with _db_lock:
        cur = _conn.execute(
            "SELECT payload FROM full_rate_snapshot WHERE base=?", (base,)
        )
        row = cur.fetchone()
    if row:
        print("[api_client] using stale cached snapshot (offline mode)")
        return json.loads(row[0])

    return None


def get_rate(base: str, target: str, rates_cache: Optional[dict] = None) -> Optional[float]:
    """
    Return the exchange rate base→target.
    Uses `rates_cache` dict if provided (avoids extra API hit).
    """
    if rates_cache and target in rates_cache:
        return rates_cache[target]

    cached = _db_get_rate(base, target)
    if cached and (time.time() - cached[1]) < RATE_TTL:
        return cached[0]

    rates = fetch_all_rates(base)
    if rates and target in rates:
        rate = rates[target]
        _db_set_rate(base, target, rate)
        return rate

    return None


# ──────────────────────────────────────────────────────────────────
#  Historical data (yfinance)
# ──────────────────────────────────────────────────────────────────

def fetch_history(from_code: str, to_code: str, days: int = 30) -> Optional[pd.DataFrame]:
    """
    Fetch daily OHLC for the currency pair using yfinance.
    Returns a DataFrame with columns [date, open, high, low, close].
    """
    symbol = ticker_symbol(from_code, to_code)
    start_str, end_str = date_range(days + 5)  # small buffer for weekends

    # Try cache first
    cached_df = _db_get_history(symbol, days)
    if cached_df is not None and len(cached_df) >= max(1, days // 2):
        return cached_df

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_str, end=end_str, interval="1d")
        if df.empty:
            raise ValueError("Empty dataframe from yfinance")

        df = df.reset_index()
        # Normalise column names (yfinance uses Title Case)
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"date": "date"})
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df[["date", "open", "high", "low", "close"]].dropna()
        df = df.tail(days)           # keep only the requested window

        _db_set_history(symbol, df)
        return df

    except Exception as exc:
        print(f"[api_client] yfinance fetch failed ({symbol}): {exc}")

    # Last resort: return stale cache if available
    return _db_get_history(symbol, days * 3)  # wider window to find anything


# ──────────────────────────────────────────────────────────────────
#  Async wrappers (thread-based so the GUI stays responsive)
# ──────────────────────────────────────────────────────────────────

def async_fetch_rates(
    base: str,
    callback: Callable[[Optional[dict[str, float]]], None],
) -> None:
    """Call fetch_all_rates in a daemon thread, then invoke callback(result)."""
    def _worker():
        result = fetch_all_rates(base)
        callback(result)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def async_fetch_history(
    from_code: str,
    to_code: str,
    days: int,
    callback: Callable[[Optional[pd.DataFrame]], None],
) -> None:
    """Call fetch_history in a daemon thread, then invoke callback(result)."""
    def _worker():
        result = fetch_history(from_code, to_code, days)
        callback(result)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
