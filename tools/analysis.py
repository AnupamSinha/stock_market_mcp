"""Analysis tools: analyze_stock, analyze_watchlist, compare_stocks."""
import json
from datetime import datetime

import yfinance as yf

from utils.helpers import _safe, _score_to_action, _history, _rsi, _macd

from app import mcp


DEFAULT_WATCHLIST = "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ITC.NS,SBIN.NS"


@mcp.tool()
def analyze_stock(symbol: str) -> str:
    """Full analysis: technicals + fundamentals, scored 0-100 with BUY/HOLD/SELL."""
    try:
        t = yf.Ticker(symbol)
        h = _history(symbol, "1y")
        if h.empty:
            return json.dumps({"symbol": symbol, "error": "no price history found"})

        close = h["Close"]
        last = float(close.iloc[-1])
        reasons, score = [], 50.0

        # Technical score
        sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
        sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

        if sma50 is not None and last > sma50:
            score += 10
            reasons.append("price above 50-day SMA (uptrend)")
        else:
            score -= 10
            reasons.append("price below 50-day SMA (downtrend)")

        if sma200 is not None:
            if last > sma200:
                score += 10
                reasons.append("price above 200-day SMA (long-term uptrend)")
            else:
                score -= 10
                reasons.append("price below 200-day SMA (long-term downtrend)")

        rsi = float(_rsi(close).iloc[-1])
        if rsi < 30:
            score += 10
            reasons.append(f"RSI {rsi:.0f} — oversold, potential rebound")
        elif rsi > 70:
            score -= 10
            reasons.append(f"RSI {rsi:.0f} — overbought, pullback risk")
        else:
            reasons.append(f"RSI {rsi:.0f} — neutral momentum")

        macd_val, sig = _macd(close)
        if macd_val.iloc[-1] > sig.iloc[-1]:
            score += 5
            reasons.append("MACD above signal line (bullish crossover)")
        else:
            score -= 5
            reasons.append("MACD below signal line (bearish)")

        ret_6m = (last / close.iloc[0] - 1) * 100
        if ret_6m > 0:
            score += 5
            reasons.append(f"6-month return {ret_6m:+.1f}%")

        # Fundamental score
        fi = t.info or {}
        pe = fi.get("trailingPE")
        sector = fi.get("sector", "N/A")
        name = fi.get("shortName", symbol)

        if pe and 0 < pe < 25:
            score += 10
            reasons.append(f"P/E {pe:.1f} — reasonable valuation")
        elif pe and pe >= 60:
            score -= 5
            reasons.append(f"P/E {pe:.1f} — expensive valuation")

        debt_eq = fi.get("debtToEquity")
        if debt_eq is not None:
            if debt_eq < 100:
                score += 5
                reasons.append(f"Debt/Equity {debt_eq:.0f} — manageable leverage")
            else:
                score -= 5
                reasons.append(f"Debt/Equity {debt_eq:.0f} — high leverage")

        margin = fi.get("profitMargins")
        if margin and margin > 0.1:
            score += 5
            reasons.append(f"Profit margin {margin*100:.1f}% — healthy")

        if fi.get("dividendYield"):
            score += 5
            reasons.append(f"Dividend yield {fi['dividendYield']:.1f}%")

        score = max(0.0, min(100.0, score))

        return json.dumps(
            {
                "symbol": symbol,
                "name": name,
                "sector": sector,
                "last_price": round(last, 2),
                "score": round(score, 1),
                "recommendation": _score_to_action(score),
                "reasons": reasons,
                "data_snapshot": {
                    "as_of": h.index[-1].date().isoformat(),
                    "generated_at": datetime.utcnow().isoformat(),
                    "sma50": _safe(round(float(sma50), 2)) if sma50 is not None else None,
                    "sma200": _safe(round(float(sma200), 2)) if sma200 is not None else None,
                    "rsi_14": _safe(round(rsi, 1)),
                    "macd": _safe(round(float(macd_val.iloc[-1]), 3)),
                    "macd_signal": _safe(round(float(sig.iloc[-1]), 3)),
                    "return_6m_pct": _safe(round(ret_6m, 1)),
                    "source": "Yahoo Finance (yfinance), daily OHLC adjusted",
                },
                "fundamentals": {
                    "pe_ratio": _safe(pe),
                    "forward_pe": _safe(fi.get("forwardPE")),
                    "market_cap": _safe(fi.get("marketCap")),
                    "dividend_yield_pct": _safe(round(fi["dividendYield"], 2))
                    if fi.get("dividendYield")
                    else None,
                    "debt_to_equity": _safe(debt_eq),
                    "profit_margin_pct": _safe(round(margin * 100, 2)) if margin else None,
                    "roe_pct": _safe(round(fi["returnOnEquity"] * 100, 2))
                    if fi.get("returnOnEquity")
                    else None,
                },
                "disclaimer": "Educational analysis only — not financial advice.",
                "sources": ["Yahoo Finance (yfinance)"],
            },
            default=str,
        )
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})


@mcp.tool()
def analyze_watchlist(symbols: str = "") -> str:
    """Analyze and rank a comma-separated list of symbols."""
    syms = [s.strip() for s in symbols.split(",") if s.strip()] or DEFAULT_WATCHLIST.split(",")
    results = []
    for s in syms[:15]:
        r = json.loads(analyze_stock(s))
        if "error" in r:
            results.append({"symbol": s, "error": r["error"]})
        else:
            results.append(
                {
                    "symbol": s,
                    "name": r["name"],
                    "price": r["last_price"],
                    "score": r["score"],
                    "recommendation": r["recommendation"],
                }
            )
    ok = [r for r in results if "score" in r]
    ok.sort(key=lambda x: x["score"], reverse=True)
    return json.dumps(
        {
            "ranked": ok,
            "errors": [r for r in results if "error" in r],
            "disclaimer": "Educational analysis only — not financial advice.",
        }
    )


@mcp.tool()
def compare_stocks(symbols: str) -> str:
    """Compare fundamentals side by side."""
    out = []
    for s in [x.strip() for x in symbols.split(",") if x.strip()][:10]:
        t = yf.Ticker(s)
        fi = t.info or {}
        h = _history(s, "1y")
        ret_1y = (
            round((float(h["Close"].iloc[-1]) / float(h["Close"].iloc[0]) - 1) * 100, 1)
            if not h.empty
            else None
        )
        out.append(
            {
                "symbol": s,
                "name": fi.get("shortName", s),
                "pe_ratio": _safe(fi.get("trailingPE")),
                "market_cap": _safe(fi.get("marketCap")),
                "profit_margin_pct": _safe(round(fi["profitMargins"] * 100, 2))
                if fi.get("profitMargins")
                else None,
                "roe_pct": _safe(round(fi["returnOnEquity"] * 100, 2))
                if fi.get("returnOnEquity")
                else None,
                "debt_to_equity": _safe(fi.get("debtToEquity")),
                "dividend_yield_pct": _safe(round(fi["dividendYield"], 2))
                if fi.get("dividendYield")
                else None,
                "return_1y_pct": ret_1y,
            }
        )
    return json.dumps({"comparison": out, "source": "Yahoo Finance (yfinance)"})