"""Fundamental analysis tools: currency_impact, dividend_calendar."""
import json
from datetime import datetime

import yfinance as yf

from utils.helpers import _safe

from app import mcp


@mcp.tool()
def currency_impact(symbol: str) -> str:
    """Show returns in both INR and USD for Indian stocks."""
    try:
        t = yf.Ticker(symbol)
        h = t.history(period="1y", auto_adjust=True)

        if h.empty:
            return json.dumps({"symbol": symbol, "error": "No price data"})

        inr = yf.Ticker("INR=X")
        inr_h = inr.history(period="1y", interval="1d")

        stock_close = h["Close"]
        if not inr_h.empty:
            usd_inr = inr_h["Close"].iloc[-1]
            if len(inr_h) > 250:
                usd_inr_start = inr_h["Close"].iloc[-250]
            else:
                usd_inr_start = inr_h["Close"].iloc[0]
        else:
            usd_inr = 83.0
            usd_inr_start = 83.0

        price_start = float(stock_close.iloc[0])
        price_end = float(stock_close.iloc[-1])

        inr_return = (price_end / price_start - 1) * 100

        usd_return = (price_end / price_start) * (usd_inr_start / usd_inr) - 1
        usd_return_pct = usd_return * 100

        currency_impact_pct = usd_return_pct - inr_return

        return json.dumps(
            {
                "symbol": symbol,
                "period": "1y",
                "inr": {
                    "price_start": _safe(round(price_start, 2)),
                    "price_end": _safe(round(price_end, 2)),
                    "return_pct": _safe(round(inr_return, 2)),
                },
                "usd": {
                    "usd_inr_start": _safe(round(usd_inr_start, 2)),
                    "usd_inr_end": _safe(round(usd_inr, 2)),
                    "return_pct": _safe(round(usd_return_pct, 2)),
                },
                "currency_impact_pct": _safe(round(currency_impact_pct, 2)),
                "interpretation": "rupee weakened" if currency_impact_pct > 0 else "rupee strengthened",
                "source": "Yahoo Finance (yfinance)",
            }
        )
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})


@mcp.tool()
def dividend_calendar(symbol: str) -> str:
    """Upcoming dividend dates, yield, and payment history."""
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        out = {"symbol": symbol, "source": "Yahoo Finance (yfinance)"}

        out["dividend_yield"] = (
            _safe(round(info.get("dividendYield", 0), 2))
            if info.get("dividendYield")
            else None
        )
        out["dividend_per_share"] = _safe(info.get("dividendRate"))
        out["payout_ratio"] = (
            _safe(round(info.get("payoutRatio", 0) * 100, 2)) if info.get("payoutRatio") else None
        )
        out["ex_dividend_date"] = str(info.get("exDividendDate"))[:10] if info.get("exDividendDate") else None

        try:
            actions = t.actions
            if actions is not None and not actions.empty:
                dividends = actions[actions["Dividends"] > 0].tail(5)
                if not dividends.empty:
                    out["recent_dividends"] = [
                        {"date": str(idx)[:10], "amount": _safe(row["Dividends"]), "type": "regular"}
                        for idx, row in dividends.iterrows()
                    ]
        except Exception:
            pass

        out["annual_dividend_rate"] = _safe(info.get("dividendRate"))
        out["frequency"] = (
            info.get("dividendFrequency", "quarterly") if info.get("dividendRate") else None
        )

        if not out.get("recent_dividends"):
            out["note"] = "Limited dividend history available — dividend_yield and annual_dividend_rate show current info."

        return json.dumps(out)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})