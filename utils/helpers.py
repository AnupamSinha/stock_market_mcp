"""Shared helper functions for stock_market_mcp tools."""
import json
import math

import pandas as pd
import yfinance as yf

from config import ALPHA_VANTAGE_API_KEY, ALPHA_VANTAGE_BASE_URL


def _safe(v):
    """Return a JSON-safe number or None."""
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _score_to_action(score: float) -> str:
    """Map a 0-100 analysis score to BUY / HOLD / SELL (same cutoffs as the server)."""
    if score >= 60:
        return "BUY"
    if score <= 20:
        return "SELL"
    return "HOLD"


def _history(symbol: str, period: str = "1y"):
    """Get daily adjusted price history for a symbol."""
    t = yf.Ticker(symbol)
    return t.history(period=period, auto_adjust=True)


def _rsi(series, period: int = 14):
    """Calculate RSI for a price series."""
    delta = series.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _macd(series):
    """Calculate MACD and signal line."""
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal


def _alpha_vantage(function: str, symbol: str, **params):
    """Optional Alpha Vantage call. Returns dict or None (no key / error)."""
    if not ALPHA_VANTAGE_API_KEY:
        return None
    import ssl
    import urllib.request
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    q = f"?function={function}&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
    q += "".join(f"&{k}={v}" for k, v in params.items())
    try:
        with urllib.request.urlopen(ALPHA_VANTAGE_BASE_URL + q, timeout=10, context=ctx) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}
