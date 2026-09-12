"""Classification tools: sector_mapping."""
import json

import yfinance as yf

from utils.helpers import _safe

from app import mcp


@mcp.tool()
def sector_mapping(symbol: str) -> str:
    """Get sector, industry, and peer tickers for a stock."""
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}

        out = {"symbol": symbol, "source": "Yahoo Finance (yfinance)"}

        out["sector"] = info.get("sector")
        out["industry"] = info.get("industry")
        out["industry_key"] = info.get("industryKey")
        out["name"] = info.get("shortName")
        out["full_time_employees"] = info.get("fullTimeEmployees")
        out["business_summary"] = (
            info.get("businessSummary", "")[:500] if info.get("businessSummary") else None
        )
        out["peers"] = info.get("peers") or []
        out["market_cap"] = _safe(info.get("marketCap"))
        out["exchange"] = info.get("exchange")
        out["quote_type"] = info.get("quoteType")
        out["trailing_pe"] = _safe(info.get("trailingPE"))
        out["forward_pe"] = _safe(info.get("forwardPE"))
        out["profit_margin"] = (
            _safe(round(info.get("profitMargins", 0) * 100, 2)) if info.get("profitMargins") else None
        )
        out["roe"] = (
            _safe(round(info.get("returnOnEquity", 0) * 100, 2)) if info.get("returnOnEquity") else None
        )
        out["beta"] = _safe(info.get("beta"))

        return json.dumps(out)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})