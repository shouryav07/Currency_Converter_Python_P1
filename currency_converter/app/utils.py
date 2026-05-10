"""
utils.py – Pure-function helpers for conversion math and date formatting.
No side-effects here; everything is deterministic so it's trivially testable.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional


# ──────────────────────────────────────────────────────────────────
#  Currency meta-data
# ──────────────────────────────────────────────────────────────────

# Mapping: ISO code → (full name, flag emoji)
CURRENCY_INFO: dict[str, tuple[str, str]] = {
    "USD": ("US Dollar",          "🇺🇸"),
    "EUR": ("Euro",               "🇪🇺"),
    "GBP": ("British Pound",      "🇬🇧"),
    "JPY": ("Japanese Yen",       "🇯🇵"),
    "CAD": ("Canadian Dollar",    "🇨🇦"),
    "AUD": ("Australian Dollar",  "🇦🇺"),
    "CHF": ("Swiss Franc",        "🇨🇭"),
    "CNY": ("Chinese Yuan",       "🇨🇳"),
    "INR": ("Indian Rupee",       "🇮🇳"),
    "MXN": ("Mexican Peso",       "🇲🇽"),
    "SGD": ("Singapore Dollar",   "🇸🇬"),
    "HKD": ("Hong Kong Dollar",   "🇭🇰"),
    "NOK": ("Norwegian Krone",    "🇳🇴"),
    "SEK": ("Swedish Krona",      "🇸🇪"),
    "DKK": ("Danish Krone",       "🇩🇰"),
    "NZD": ("New Zealand Dollar", "🇳🇿"),
    "ZAR": ("South African Rand", "🇿🇦"),
    "BRL": ("Brazilian Real",     "🇧🇷"),
    "KRW": ("South Korean Won",   "🇰🇷"),
    "TRY": ("Turkish Lira",       "🇹🇷"),
    "AED": ("UAE Dirham",         "🇦🇪"),
    "SAR": ("Saudi Riyal",        "🇸🇦"),
    "THB": ("Thai Baht",          "🇹🇭"),
    "IDR": ("Indonesian Rupiah",  "🇮🇩"),
    "MYR": ("Malaysian Ringgit",  "🇲🇾"),
    "PHP": ("Philippine Peso",    "🇵🇭"),
    "PKR": ("Pakistani Rupee",    "🇵🇰"),
    "EGP": ("Egyptian Pound",     "🇪🇬"),
    "CZK": ("Czech Koruna",       "🇨🇿"),
    "PLN": ("Polish Zloty",       "🇵🇱"),
}

POPULAR_PAIRS = [
    ("USD", "EUR"),
    ("USD", "GBP"),
    ("USD", "JPY"),
    ("EUR", "GBP"),
    ("GBP", "JPY"),
    ("USD", "INR"),
    ("USD", "CAD"),
    ("USD", "AUD"),
]

TIMEFRAME_DAYS = {"1D": 1, "1W": 7, "1M": 30}


# ──────────────────────────────────────────────────────────────────
#  Conversion helpers
# ──────────────────────────────────────────────────────────────────

def convert(amount: float, rate: float) -> float:
    """Multiply amount by exchange rate, returning the converted value."""
    return amount * rate


def format_amount(value: float, currency: str) -> str:
    """
    Format a monetary value with sensible decimal places.
    High-value currencies (JPY, KRW, IDR …) get 0 decimals;
    everything else gets 2–4 decimals depending on magnitude.
    """
    zero_decimal = {"JPY", "KRW", "IDR", "VND", "CLP", "HUF", "TWD"}
    if currency in zero_decimal:
        return f"{value:,.0f}"
    if value >= 100:
        return f"{value:,.2f}"
    if value >= 1:
        return f"{value:,.4f}"
    # Very small values (crypto-style)
    return f"{value:,.6f}"


def format_rate(rate: float) -> str:
    """Human-readable exchange rate string."""
    if rate >= 100:
        return f"{rate:,.2f}"
    if rate >= 1:
        return f"{rate:,.4f}"
    return f"{rate:,.6f}"


def rate_change_pct(current: float, previous: float) -> Optional[float]:
    """Return percentage change between two rates, or None if previous is 0."""
    if not previous:
        return None
    return ((current - previous) / previous) * 100


def pct_label(pct: Optional[float]) -> str:
    """Format a percentage change as a ±XX.XX% string."""
    if pct is None:
        return "N/A"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


# ──────────────────────────────────────────────────────────────────
#  Date helpers
# ──────────────────────────────────────────────────────────────────

def date_range(days: int) -> tuple[str, str]:
    """Return (start_date, end_date) as 'YYYY-MM-DD' strings."""
    end   = datetime.utcnow()
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def friendly_timestamp(dt: Optional[datetime] = None) -> str:
    """E.g. 'Updated: 14 Jun 2025, 09:42 UTC'"""
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime("Updated: %d %b %Y, %H:%M UTC")


def ticker_symbol(from_code: str, to_code: str) -> str:
    """Build a yfinance forex ticker, e.g. 'EURUSD=X'."""
    return f"{from_code}{to_code}=X"


# ──────────────────────────────────────────────────────────────────
#  Trend detection
# ──────────────────────────────────────────────────────────────────

def trend_direction(series: list[float]) -> str:
    """
    'up', 'down', or 'flat' based on linear regression slope of the series.
    Uses a simple least-squares slope calculation without scipy dependency.
    """
    n = len(series)
    if n < 2:
        return "flat"

    x_mean = (n - 1) / 2
    y_mean = sum(series) / n
    numerator   = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(series))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return "flat"

    slope = numerator / denominator
    threshold = y_mean * 0.0001  # 0.01% of mean = effectively flat

    if slope > threshold:
        return "up"
    if slope < -threshold:
        return "down"
    return "flat"


def currency_label(code: str) -> str:
    """'🇺🇸 USD – US Dollar'"""
    name, flag = CURRENCY_INFO.get(code, ("Unknown", "🏳️"))
    return f"{flag} {code} – {name}"


def short_label(code: str) -> str:
    """'🇺🇸 USD'"""
    _, flag = CURRENCY_INFO.get(code, ("Unknown", "🏳️"))
    return f"{flag} {code}"
