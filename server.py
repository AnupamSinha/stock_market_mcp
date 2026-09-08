"""
stock_market_mcp — Stock Analysis MCP Server

Analyzes stocks and returns BUY / HOLD / SELL style assessments using:
  1. Yahoo Finance (via yfinance) — free, no API key required
  2. Alpha Vantage (optional) — extra market data when ALPHA_VANTAGE_API_KEY is set

Run:  python server.py        (stdio MCP server)
"""
import json
import math
import os
from datetime import datetime, timedelta

import yfinance as yf
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------- config
def _load_env(path=os.path.join(os.path.dirname(__file__), ".env")):
    """Minimal .env loader: KEY=VALUE lines are set as env vars (not overriding existing)."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass

_load_env()
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

mcp = FastMCP("stock_market_mcp")

DEFAULT_WATCHLIST = "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ITC.NS,SBIN.NS"

# ---------------------------------------------------------------- helpers
def _safe(v):
    """Return a JSON-safe number or None."""
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v

def _score_to_action(score: float) -> str:
    if score >= 60:
        return "BUY"
    if score <= 20:
        return "SELL"
    return "HOLD"

def _history(symbol: str, period: str = "1y"):
    t = yf.Ticker(symbol)
    return t.history(period=period, auto_adjust=True)

def _rsi(series, period: int = 14):
    delta = series.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def _macd(series):
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

# ---------------------------------------------------------------- tools
@mcp.tool()
def get_quote(symbol: str) -> str:
    """Current price quote for a stock symbol (e.g. RELIANCE.NS for NSE, AAPL for US)."""
    t = yf.Ticker(symbol)
    info = {}
    try:
        fi = t.fast_info
        info = {"last_price": _safe(fi.last_price), "currency": fi.currency,
                "previous_close": _safe(fi.previous_close)}
        if info.get("last_price") and info.get("previous_close"):
            info["change_pct"] = round(
                (info["last_price"] / info["previous_close"] - 1) * 100, 2)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})
    return json.dumps({"symbol": symbol, **info, "source": "Yahoo Finance (yfinance)"})

@mcp.tool()
def technical_analysis(symbol: str, period: str = "6mo") -> str:
    """Technical indicators (SMA 20/50/200, RSI-14, MACD, 52w high/low, volatility) for a symbol."""
    try:
        h = _history(symbol, period)
        if h.empty:
            return json.dumps({"symbol": symbol, "error": "no price history found"})
        close = h["Close"]
        last = float(close.iloc[-1])
        sma = {p: _safe(round(float(close.rolling(p).mean().iloc[-1]), 2)) for p in (20, 50, 200) if len(close) >= p}
        rsi = _safe(round(float(_rsi(close).iloc[-1]), 1))
        macd, signal = _macd(close)
        return json.dumps({
            "symbol": symbol,
            "last_close": round(last, 2),
            "sma": sma,
            "rsi_14": rsi,
            "macd": _safe(round(float(macd.iloc[-1]), 3)),
            "macd_signal": _safe(round(float(signal.iloc[-1]), 3)),
            "macd_trend": "bullish" if macd.iloc[-1] > signal.iloc[-1] else "bearish",
            "high_52w": _safe(round(float(h["High"].max()), 2)),
            "low_52w": _safe(round(float(h["Low"].min()), 2)),
            "daily_volatility_pct": _safe(round(float(close.pct_change().std() * 100), 2)),
            "source": "Yahoo Finance (yfinance)",
        })
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})

@mcp.tool()
def analyze_stock(symbol: str) -> str:
    """Full analysis of one stock: technicals + fundamentals, scored 0-100 with a BUY/HOLD/SELL recommendation."""
    try:
        t = yf.Ticker(symbol)
        h = _history(symbol, "1y")
        if h.empty:
            return json.dumps({"symbol": symbol, "error": "no price history found"})
        close = h["Close"]
        last = float(close.iloc[-1])
        reasons, score = [], 50.0  # start neutral

        # --- technical score
        sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
        sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
        if sma50 is not None and last > sma50:
            score += 10; reasons.append("price above 50-day SMA (uptrend)")
        else:
            score -= 10; reasons.append("price below 50-day SMA (downtrend)")
        if sma200 is not None:
            if last > sma200:
                score += 10; reasons.append("price above 200-day SMA (long-term uptrend)")
            else:
                score -= 10; reasons.append("price below 200-day SMA (long-term downtrend)")
        rsi = float(_rsi(close).iloc[-1])
        if rsi < 30:
            score += 10; reasons.append(f"RSI {rsi:.0f} — oversold, potential rebound")
        elif rsi > 70:
            score -= 10; reasons.append(f"RSI {rsi:.0f} — overbought, pullback risk")
        else:
            reasons.append(f"RSI {rsi:.0f} — neutral momentum")
        macd, sig = _macd(close)
        if macd.iloc[-1] > sig.iloc[-1]:
            score += 5; reasons.append("MACD above signal line (bullish crossover)")
        else:
            score -= 5; reasons.append("MACD below signal line (bearish)")
        ret_6m = (last / close.iloc[0] - 1) * 100
        if ret_6m > 0:
            score += 5; reasons.append(f"6-month return {ret_6m:+.1f}%")

        # --- fundamental score
        fi = t.info or {}
        pe = fi.get("trailingPE")
        sector = fi.get("sector", "N/A")
        name = fi.get("shortName", symbol)
        if pe and 0 < pe < 25:
            score += 10; reasons.append(f"P/E {pe:.1f} — reasonable valuation")
        elif pe and pe >= 60:
            score -= 5; reasons.append(f"P/E {pe:.1f} — expensive valuation")
        debt_eq = fi.get("debtToEquity")
        if debt_eq is not None:
            if debt_eq < 100:
                score += 5; reasons.append(f"Debt/Equity {debt_eq:.0f} — manageable leverage")
            else:
                score -= 5; reasons.append(f"Debt/Equity {debt_eq:.0f} — high leverage")
        margin = fi.get("profitMargins")
        if margin and margin > 0.1:
            score += 5; reasons.append(f"Profit margin {margin*100:.1f}% — healthy")
        if fi.get("dividendYield"):
            score += 5; reasons.append(f"Dividend yield {fi['dividendYield']*100:.1f}%")

        score = max(0.0, min(100.0, score))
        return json.dumps({
            "symbol": symbol, "name": name, "sector": sector,
            "last_price": round(last, 2),
            "score": round(score, 1),
            "recommendation": _score_to_action(score),
            "reasons": reasons,
            "fundamentals": {
                "pe_ratio": _safe(pe), "forward_pe": _safe(fi.get("forwardPE")),
                "market_cap": _safe(fi.get("marketCap")),
                "dividend_yield_pct": _safe(round(fi["dividendYield"] * 100, 2)) if fi.get("dividendYield") else None,
                "debt_to_equity": _safe(debt_eq), "profit_margin_pct": _safe(round(margin * 100, 2)) if margin else None,
                "roe_pct": _safe(round(fi["returnOnEquity"] * 100, 2)) if fi.get("returnOnEquity") else None,
            },
            "disclaimer": "Educational analysis only — not financial advice.",
            "sources": ["Yahoo Finance (yfinance)"],
        }, default=str)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})

@mcp.tool()
def analyze_watchlist(symbols: str = "") -> str:
    """Analyze a comma-separated list of symbols and rank them by score. Empty uses a default Indian NSE watchlist."""
    syms = [s.strip() for s in symbols.split(",") if s.strip()] or DEFAULT_WATCHLIST.split(",")
    results = []
    for s in syms[:15]:
        r = json.loads(analyze_stock(s))
        if "error" in r:
            results.append({"symbol": s, "error": r["error"]})
        else:
            results.append({"symbol": s, "name": r["name"], "price": r["last_price"],
                            "score": r["score"], "recommendation": r["recommendation"]})
    ok = [r for r in results if "score" in r]
    ok.sort(key=lambda x: x["score"], reverse=True)
    return json.dumps({"ranked": ok, "errors": [r for r in results if "error" in r],
                       "disclaimer": "Educational analysis only — not financial advice."})

@mcp.tool()
def compare_stocks(symbols: str) -> str:
    """Compare fundamentals (P/E, margins, ROE, market cap, 1y return) of comma-separated symbols side by side."""
    out = []
    for s in [x.strip() for x in symbols.split(",") if x.strip()][:10]:
        t = yf.Ticker(s)
        fi = t.info or {}
        h = _history(s, "1y")
        ret_1y = round((float(h["Close"].iloc[-1]) / float(h["Close"].iloc[0]) - 1) * 100, 1) if not h.empty else None
        out.append({"symbol": s, "name": fi.get("shortName", s),
                    "pe_ratio": _safe(fi.get("trailingPE")),
                    "market_cap": _safe(fi.get("marketCap")),
                    "profit_margin_pct": _safe(round(fi["profitMargins"] * 100, 2)) if fi.get("profitMargins") else None,
                    "roe_pct": _safe(round(fi["returnOnEquity"] * 100, 2)) if fi.get("returnOnEquity") else None,
                    "debt_to_equity": _safe(fi.get("debtToEquity")),
                    "dividend_yield_pct": _safe(round(fi["dividendYield"] * 100, 2)) if fi.get("dividendYield") else None,
                    "return_1y_pct": ret_1y})
    return json.dumps({"comparison": out, "source": "Yahoo Finance (yfinance)"})

@mcp.tool()
def market_movers(market: str = "india") -> str:
    """Top gainers/losers/active for a market. market: 'india' (NSE) or 'us'."""
    index_symbol = "^NSEI" if market.lower() == "india" else "^GSPC"
    try:
        idx = yf.Ticker(index_symbol)
        info = idx.info or {}
        constituents_hint = "See index page for constituents; pass them to analyze_watchlist."
        hist = idx.history(period="5d")
        return json.dumps({
            "market": market,
            "index": "NIFTY 50" if market.lower() == "india" else "S&P 500",
            "index_level": _safe(round(float(hist["Close"].iloc[-1]), 2)) if not hist.empty else None,
            "hint": constituents_hint,
            "suggested_workflow": "run analyze_watchlist on your candidate symbols",
            "source": "Yahoo Finance (yfinance)",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def stock_news(symbol: str, limit: int = 5) -> str:
    """Recent news headlines for a stock symbol."""
    try:
        items = yf.Ticker(symbol).news or []
        out = []
        for n in items[:limit]:
            content = n.get("content", n)
            out.append({"title": content.get("title"),
                        "publisher": (content.get("provider") or {}).get("displayName"),
                        "link": (content.get("canonicalUrl") or {}).get("url")})
        return json.dumps({"symbol": symbol, "news": out, "source": "Yahoo Finance (yfinance)"})
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})

@mcp.tool()
def alpha_vantage_overview(symbol: str) -> str:
    """Optional Alpha Vantage company OVERVIEW (requires ALPHA_VANTAGE_API_KEY; free tier 5 req/min, 500/day)."""
    if not ALPHA_VANTAGE_API_KEY:
        return json.dumps({"error": "ALPHA_VANTAGE_API_KEY not set — this tool is optional; use analyze_stock instead."})
    data = _alpha_vantage("OVERVIEW", symbol)
    return json.dumps({"symbol": symbol, "data": data, "source": "Alpha Vantage API"})

# ---------------------------------------------------------------- main
if __name__ == "__main__":
    mcp.run()  # stdio transport
