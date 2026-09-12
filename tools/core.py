"""Core tools: get_quote, search_symbol, technical_analysis."""
import json

import yfinance as yf

from utils.helpers import _safe

from app import mcp


@mcp.tool()
def get_quote(symbol: str) -> str:
    """Current price quote for a stock symbol."""
    t = yf.Ticker(symbol)
    info = {}
    try:
        fi = t.fast_info
        info = {
            "last_price": _safe(fi.last_price),
            "currency": fi.currency,
            "previous_close": _safe(fi.previous_close),
        }
        if info.get("last_price") and info.get("previous_close"):
            info["change_pct"] = round(
                (info["last_price"] / info["previous_close"] - 1) * 100, 2
            )
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})
    return json.dumps(
        {"symbol": symbol, **info, "source": "Yahoo Finance (yfinance)"}
    )


@mcp.tool()
def search_symbol(query: str, limit: int = 8) -> str:
    """Resolve company name to tradeable symbols. India-first ranking."""
    try:
        from yfinance import Search

        s = Search(query, max_results=25)
        hits = []
        for r in s.quotes or []:
            sym = r.get("symbol", "")
            if not sym:
                continue
            hits.append(
                {
                    "symbol": sym,
                    "name": r.get("shortname") or r.get("longname") or r.get("displayname"),
                    "exchange": r.get("exchDisp") or r.get("exchange"),
                    "type": r.get("quoteType"),
                }
            )

        def rank(h):
            if h["symbol"].endswith(".NS"):
                return (0, h["symbol"])
            if h["symbol"].endswith(".BO"):
                return (1, h["symbol"])
            return (2, h["symbol"])

        hits.sort(key=rank)

        if not hits:
            q = query.strip().upper()
            for cand in (q if "." in q else None, f"{q}.NS", f"{q}.BO"):
                if not cand:
                    continue
                try:
                    fi = yf.Ticker(cand).fast_info
                    if _safe(fi.last_price) is not None:
                        hits.append(
                            {
                                "symbol": cand,
                                "name": None,
                                "exchange": "NSE" if cand.endswith(".NS") else "BSE",
                                "type": None,
                            }
                        )
                        break
                except Exception:
                    continue

        return json.dumps(
            {
                "query": query,
                "results": hits[:limit],
                "source": "Yahoo Finance (yfinance) Search",
            }
        )
    except Exception as e:
        return json.dumps({"query": query, "error": str(e)})


@mcp.tool()
def technical_analysis(symbol: str, period: str = "6mo") -> str:
    """Technical indicators: SMA, RSI, MACD, 52w high/low."""
    try:
        from utils.helpers import _history, _rsi, _macd

        h = _history(symbol, period)
        if h.empty:
            return json.dumps({"symbol": symbol, "error": "no price history found"})

        close = h["Close"]
        last = float(close.iloc[-1])
        sma = {
            p: _safe(round(float(close.rolling(p).mean().iloc[-1]), 2))
            for p in (20, 50, 200)
            if len(close) >= p
        }
        rsi_val = _safe(round(float(_rsi(close).iloc[-1]), 1))
        macd_val, signal = _macd(close)

        return json.dumps(
            {
                "symbol": symbol,
                "last_close": round(last, 2),
                "sma": sma,
                "rsi_14": rsi_val,
                "macd": _safe(round(float(macd_val.iloc[-1]), 3)),
                "macd_signal": _safe(round(float(signal.iloc[-1]), 3)),
                "macd_trend": "bullish" if macd_val.iloc[-1] > signal.iloc[-1] else "bearish",
                "high_52w": _safe(round(float(h["High"].max()), 2)),
                "low_52w": _safe(round(float(h["Low"].min()), 2)),
                "daily_volatility_pct": _safe(
                    round(float(close.pct_change().std() * 100), 2)
                ),
                "source": "Yahoo Finance (yfinance)",
            }
        )
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})

@mcp.tool()
def alpha_vantage_overview(symbol: str) -> str:
    """Optional Alpha Vantage company OVERVIEW (requires ALPHA_VANTAGE_API_KEY; free tier ~25 req/day, 500/day). Works for US symbols only — NSE/BSE return empty data."""
    from config import ALPHA_VANTAGE_API_KEY
    if not ALPHA_VANTAGE_API_KEY:
        return json.dumps({"error": "ALPHA_VANTAGE_API_KEY not set — this tool is optional; use analyze_stock instead."})
    from utils.helpers import _alpha_vantage
    data = _alpha_vantage("OVERVIEW", symbol)
    return json.dumps({"symbol": symbol, "data": data, "source": "Alpha Vantage API"})
