"""Screening tools: stock_screener, correlation_analysis."""
import json

import pandas as pd
import yfinance as yf

from utils.helpers import _safe, _score_to_action, _history, _rsi, _macd

from app import mcp

DEFAULT_WATCHLIST = "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ITC.NS,SBIN.NS"


@mcp.tool()
def stock_screener(
    symbols: str = "",
    min_pe: float = None,
    max_pe: float = None,
    min_rsi: float = None,
    max_rsi: float = None,
    min_dividend_yield: float = None,
    min_roe: float = None,
    min_score: int = None,
) -> str:
    """Screen stocks by criteria."""
    syms = [s.strip() for s in symbols.split(",") if s.strip()] or DEFAULT_WATCHLIST.split(",")
    matches = []

    for s in syms[:20]:
        try:
            t = yf.Ticker(s)
            info = t.info or {}
            h = _history(s, "6mo")

            if h.empty:
                continue

            close = h["Close"]
            rsi_val = float(_rsi(close).iloc[-1]) if len(close) >= 14 else None

            pe = info.get("trailingPE")
            dividend_yield = info.get("dividendYield")
            roe = info.get("returnOnEquity")

            # Calculate score
            score = 50.0
            sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
            if sma50 is not None and float(close.iloc[-1]) > sma50:
                score += 10
            else:
                score -= 10

            if rsi_val is not None:
                if rsi_val < 30:
                    score += 10
                elif rsi_val > 70:
                    score -= 10
                else:
                    score += 2

            macd_val, sig = _macd(close)
            if macd_val.iloc[-1] > sig.iloc[-1]:
                score += 5
            else:
                score -= 5

            if pe and 0 < pe < 25:
                score += 10
            elif pe and pe >= 60:
                score -= 5

            if dividend_yield:
                score += 5

            if roe and roe > 0.15:
                score += 5

            score = max(0.0, min(100.0, score))

            # Apply filters
            if min_pe is not None and (pe is None or pe < min_pe):
                continue
            if max_pe is not None and (pe is None or pe > max_pe):
                continue
            if min_rsi is not None and (rsi_val is None or rsi_val < min_rsi):
                continue
            if max_rsi is not None and (rsi_val is None or rsi_val > max_rsi):
                continue
            if min_dividend_yield is not None and (
                dividend_yield is None or dividend_yield < min_dividend_yield
            ):
                continue
            if min_roe is not None and (roe is None or roe * 100 < min_roe):
                continue
            if min_score is not None and score < min_score:
                continue

            matches.append(
                {
                    "symbol": s,
                    "name": info.get("shortName", s),
                    "price": _safe(round(float(close.iloc[-1]), 2)),
                    "pe_ratio": _safe(pe),
                    "rsi_14": _safe(round(rsi_val, 1)) if rsi_val else None,
                    "dividend_yield_pct": (
                        _safe(round(dividend_yield, 2)) if dividend_yield else None
                    ),
                    "roe_pct": _safe(round(roe * 100, 2)) if roe else None,
                    "score": _safe(round(score, 1)),
                    "recommendation": _score_to_action(score),
                }
            )
        except Exception:
            continue

    return json.dumps(
        {
            "matches": matches,
            "n_input": len(syms),
            "n_matches": len(matches),
            "filters_applied": {
                "min_pe": min_pe,
                "max_pe": max_pe,
                "min_rsi": min_rsi,
                "max_rsi": max_rsi,
                "min_dividend_yield": min_dividend_yield,
                "min_roe": min_roe,
                "min_score": min_score,
            },
            "source": "Yahoo Finance (yfinance)",
        }
    )


@mcp.tool()
def correlation_analysis(symbol: str, benchmark: str = "^NSEI", period: str = "1y") -> str:
    """Calculate correlation, beta, rolling correlation vs benchmark."""
    try:
        stock = yf.Ticker(symbol)
        bench = yf.Ticker(benchmark)

        stock_h = stock.history(period=period, auto_adjust=True)
        bench_h = bench.history(period=period, auto_adjust=True)

        if stock_h.empty or bench_h.empty:
            return json.dumps({"error": "No price data available"})

        aligned = stock_h["Close"].align(bench_h["Close"], join="inner")
        stock_returns = aligned[0].pct_change().dropna()
        bench_returns = aligned[1].pct_change().dropna()

        corr = stock_returns.corr(bench_returns)

        rolling_corr = stock_returns.rolling(30).corr(bench_returns)
        rolling_corr_series = rolling_corr.dropna()

        beta = stock_returns.cov(bench_returns) / bench_returns.var()
        r_squared = corr**2

        return json.dumps(
            {
                "symbol": symbol,
                "benchmark": benchmark,
                "correlation": _safe(round(corr, 3)),
                "beta": _safe(round(beta, 3)),
                "r_squared": _safe(round(r_squared, 3)),
                "correlation_trend": (
                    "high" if abs(corr) > 0.7 else ("moderate" if abs(corr) > 0.4 else "low")
                ),
                "rolling_correlation_30d": {
                    "current": _safe(round(rolling_corr_series.iloc[-1], 3)),
                    "mean": _safe(round(rolling_corr_series.mean(), 3)),
                    "min": _safe(round(rolling_corr_series.min(), 3)),
                    "max": _safe(round(rolling_corr_series.max(), 3)),
                },
                "period_days": len(stock_returns),
                "source": "Yahoo Finance (yfinance)",
            }
        )
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})