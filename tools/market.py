"""Market tools: market_movers, stock_news, earnings_calendar."""
import json
import time
from datetime import datetime

import pandas as pd
import requests
import yfinance as yf

from utils.helpers import _safe

from app import mcp

# Cache for movers data
_MOVERS_CACHE = {"ts": 0.0, "data": None}
_NSE_MOVERS_CACHE = {"ts": 0.0, "data": None}
_MOVERS_TTL = 600  # seconds


def _bse_movers():
    """Top BSE gainers/losers via bsedata."""
    import pandas as pd

    now = time.time()
    if _MOVERS_CACHE["data"] is not None and now - _MOVERS_CACHE["ts"] < _MOVERS_TTL:
        return {**_MOVERS_CACHE["data"], "cached": True}

    try:
        from bsedata.bse import BSE

        b = BSE()

        def _rows(rows):
            return [
                {
                    "symbol": f"{r['scripCode']}.BO",
                    "company": r.get("securityID"),
                    "price": _safe(r.get("LTP")),
                    "change_pct": _safe(r.get("pChange")),
                }
                for r in rows[:5]
            ]

        data = {
            "gainers": _rows(b.topGainers()),
            "losers": _rows(b.topLosers()),
            "cached": False,
        }
        _MOVERS_CACHE.update(ts=now, data=data)
        return data
    except Exception as e:
        return {"error": str(e)}


def _nse_movers():
    """Top NSE gainers/losers from nseindia.com."""
    now = time.time()
    if _NSE_MOVERS_CACHE["data"] is not None and now - _NSE_MOVERS_CACHE["ts"] < _MOVERS_TTL:
        return {**_NSE_MOVERS_CACHE["data"], "cached": True}

    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "*/*",
            "Referer": "https://www.nseindia.com/",
        }
    )
    s.get("https://www.nseindia.com", timeout=10)

    def _rows(url):
        d = s.get(url, timeout=10).json()
        rows = d.get("NIFTY", {}).get("data") if isinstance(d.get("NIFTY"), dict) else None
        if rows is None:
            rows = d.get("data", [])
        return [
            {
                "symbol": f"{r['symbol']}.NS",
                "company": r.get("symbol"),
                "price": _safe(r.get("ltp")),
                "change_pct": _safe(r.get("perChange")),
            }
            for r in rows[:5]
        ]

    data = {
        "gainers": _rows(
            "https://www.nseindia.com/api/live-analysis-variations?index=gainers"
        ),
        "losers": _rows(
            "https://www.nseindia.com/api/live-analysis-variations?index=loosers"
        ),
        "cached": False,
    }
    _NSE_MOVERS_CACHE.update(ts=now, data=data)
    return data


@mcp.tool()
def market_movers(market: str = "india") -> str:
    """Market snapshot: NSE/BSE gainers/losers and index level."""
    index_symbol = "^NSEI" if market.lower() == "india" else "^GSPC"
    index_name = "NIFTY 50" if market.lower() == "india" else "S&P 500"
    out = {"market": market, "index": index_name, "source": "Yahoo Finance (yfinance)"}

    try:
        hist = yf.Ticker(index_symbol).history(period="5d")
        out["index_level"] = _safe(round(float(hist["Close"].iloc[-1]), 2)) if not hist.empty else None
    except Exception as e:
        out["index_error"] = str(e)

    if market.lower() == "india":
        try:
            out["nse_movers"] = _nse_movers()
            out["movers_source"] = "nseindia.com public API + bsedata (10-min caches)"
        except Exception as e:
            out["nse_movers"] = None
            out["nse_movers_error"] = str(e)

        try:
            out["bse_movers"] = _bse_movers()
            if "movers_source" not in out:
                out["movers_source"] = "bsedata (scrapes bseindia.com, 10-min cache)"
        except Exception as e:
            out["bse_movers"] = None
            out["bse_movers_error"] = str(e)
            out["note"] = "BSE movers unavailable — pass candidate symbols to analyze_watchlist."
    else:
        out["suggested_workflow"] = "run analyze_watchlist on your candidate symbols"

    return json.dumps(out)


@mcp.tool()
def stock_news(symbol: str, limit: int = 5) -> str:
    """Recent news headlines for a stock."""
    try:
        items = yf.Ticker(symbol).news or []
        out = []
        for n in items[:limit]:
            content = n.get("content", n)
            out.append(
                {
                    "title": content.get("title"),
                    "publisher": (content.get("provider") or {}).get("displayName"),
                    "link": (content.get("canonicalUrl") or {}).get("url"),
                }
            )
        return json.dumps(
            {"symbol": symbol, "news": out, "source": "Yahoo Finance (yfinance)"}
        )
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})


@mcp.tool()
def earnings_calendar(symbol: str) -> str:
    """Upcoming earnings dates, EPS estimates, and recent history."""
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        out = {"symbol": symbol, "source": "Yahoo Finance (yfinance)"}

        earnings_dates = t.earnings_dates
        if earnings_dates is not None:
            try:
                df = earnings_dates
                if not df.empty:
                    first_idx = df.index[0]
                    next_row = df.iloc[0]
                    eps_est = next_row.get("EPS Estimate")
                    eps_rep = next_row.get("Reported EPS")

                    ed_str = str(first_idx)[:10]
                    if pd.isna(eps_rep):
                        out["next_earnings_date"] = ed_str
                        out["eps_estimate"] = _safe(eps_est)
                        try:
                            ed_date = first_idx.date()
                            now = datetime.now().date()
                            delta = (ed_date - now).days
                            out["days_until"] = delta
                            out["time_until"] = f"{delta} days" if delta > 0 else "today"
                        except Exception:
                            pass

                    recent = []
                    for i, (idx, row) in enumerate(df.iterrows()):
                        if i == 0 and pd.isna(row.get("Reported EPS")):
                            continue
                        if i >= 5:
                            break
                        if pd.notna(row.get("Reported EPS")):
                            recent.append(
                                {
                                    "period": str(idx)[:10],
                                    "eps_estimate": _safe(row.get("EPS Estimate")),
                                    "eps_reported": _safe(row.get("Reported EPS")),
                                    "surprise_pct": _safe(row.get("Surprise(%)")),
                                }
                            )
                    if recent:
                        out["recent_earnings"] = recent
            except Exception as e:
                out["parse_error"] = str(e)

        # Fallback: quarterly financials
        if not out.get("recent_earnings"):
            try:
                q = t.quarterly_financials
                if not q.empty and "EPS Diluted" in q.index:
                    eps_series = q.loc["EPS Diluted"].iloc[:4]
                    out["recent_earnings"] = [
                        {"period": str(col)[:10], "eps_reported": _safe(float(val))}
                        for col, val in zip(eps_series.index, eps_series.values)
                    ]
            except Exception:
                pass

        out["eps_estimate"] = out.get("eps_estimate") or _safe(info.get("epsEstimate"))
        out["earnings_high"] = _safe(info.get("earningsHigh"))
        out["earnings_low"] = _safe(info.get("earningsLow"))
        out["revenue_growth"] = (
            _safe(round(info.get("revenueGrowth", 0) * 100, 2))
            if info.get("revenueGrowth")
            else None
        )

        if not out.get("next_earnings_date"):
            out["note"] = "No scheduled earnings date found — check recent_earnings for last 4 quarters."

        return json.dumps(out)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})