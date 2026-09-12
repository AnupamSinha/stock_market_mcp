"""Journal tools: log_decision, review_decisions, analyst_reports."""
import json
import os
from datetime import datetime

import pandas as pd
import yfinance as yf

from utils.helpers import _safe

from app import mcp

JOURNAL_COLLECTION = "decision_journal"
_JOURNAL_FALLBACK = os.path.join(os.path.dirname(__file__), "..", "decision_journal.json")


def _journal_collection():
    """MongoDB collection for the decision journal, or None to use JSON fallback."""
    try:
        import pymongo

        MONGODB_URI = os.environ.get(
            "MONGODB_URI", "mongodb://localhost:27017"
        )
        MONGODB_DB = os.environ.get("MONGODB_DB_NAME", "stock_data")
        client = pymongo.MongoClient(
            MONGODB_URI, serverSelectionTimeoutMS=2000
        )
        client.admin.command("ping")
        return client[MONGODB_DB][JOURNAL_COLLECTION]
    except Exception:
        return None


def _journal_insert(doc: dict):
    """Insert a journal entry."""
    doc = {"_ts": datetime.utcnow().isoformat(), **doc}
    col = _journal_collection()
    if col is not None:
        col.insert_one(doc)
        doc.pop("_id", None)
    else:
        docs = []
        try:
            with open(_JOURNAL_FALLBACK) as f:
                docs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        docs.append(doc)
        with open(_JOURNAL_FALLBACK, "w") as f:
            json.dump(docs, f, indent=2)
    return doc


def _journal_find(query: dict = None):
    """Find journal entries."""
    query = query or {}
    col = _journal_collection()
    if col is not None:
        out = []
        for d in col.find(query).sort("_ts", -1).limit(500):
            d.pop("_id", None)
            out.append(d)
        return out
    try:
        with open(_JOURNAL_FALLBACK) as f:
            docs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    def _match(d):
        return all(d.get(k) == v for k, v in query.items())

    return [d for d in docs if _match(d)][::-1]


@mcp.tool()
def log_decision(symbol: str, action: str, rationale: str = "", score: float = None) -> str:
    """Record a BUY/HOLD/SELL decision in the journal."""
    action = action.upper()
    if action not in ("BUY", "HOLD", "SELL"):
        return json.dumps({"error": "action must be BUY, HOLD or SELL"})
    try:
        price = _safe(yf.Ticker(symbol).fast_info.last_price)
    except Exception:
        price = None
    doc = _journal_insert(
        {
            "kind": "decision",
            "symbol": symbol,
            "action": action,
            "rationale": rationale,
            "score": score,
            "price_at_decision": price,
            "status": "open",
        }
    )
    return json.dumps({"logged": True, "decision": doc})


@mcp.tool()
def review_decisions(symbol: str = "") -> str:
    """Review logged decisions against current prices."""
    query = {"kind": "decision"} | ({"symbol": symbol} if symbol else {})
    docs = [d for d in _journal_find(query) if d.get("status") == "open"]
    if not docs:
        return json.dumps(
            {"review": [], "note": "no open decisions logged yet — use log_decision"}
        )

    review = []
    for d in docs[:50]:
        entry = dict(d)
        try:
            now = _safe(yf.Ticker(d["symbol"]).fast_info.last_price)
            entry["price_now"] = now
            if now and d.get("price_at_decision"):
                ret = (now / d["price_at_decision"] - 1) * 100
                entry["return_since_pct"] = round(ret, 2)
                if d["action"] == "BUY":
                    entry["outcome"] = (
                        "CORRECT" if ret > 1 else ("WRONG" if ret < -1 else "NEUTRAL")
                    )
                elif d["action"] == "SELL":
                    entry["outcome"] = (
                        "CORRECT" if ret < -1 else ("WRONG" if ret > 1 else "NEUTRAL")
                    )
                else:
                    entry["outcome"] = (
                        "NEUTRAL" if abs(ret) <= 5 else "BROKEN (price moved >5%)"
                    )
        except Exception as e:
            entry["error"] = str(e)
        review.append(entry)

    return json.dumps(
        {
            "review": review,
            "n_open": len(docs),
            "disclaimer": "Educational analysis only — not financial advice.",
        }
    )


@mcp.tool()
def analyst_reports(symbol: str) -> str:
    """Three analyst reports: fundamentals, technical, sentiment."""
    from tools.core import technical_analysis
    from tools.market import stock_news

    tech = json.loads(technical_analysis(symbol, "1y"))

    t = yf.Ticker(symbol)
    fi = t.info or {}
    fund = {
        "name": fi.get("shortName", symbol),
        "sector": fi.get("sector", "N/A"),
        "pe_ratio": _safe(fi.get("trailingPE")),
        "forward_pe": _safe(fi.get("forwardPE")),
        "market_cap": _safe(fi.get("marketCap")),
        "dividend_yield_pct": (
            _safe(round(fi["dividendYield"], 2)) if fi.get("dividendYield") else None
        ),
        "debt_to_equity": _safe(fi.get("debtToEquity")),
        "profit_margin_pct": (
            _safe(round(fi["profitMargins"] * 100, 2)) if fi.get("profitMargins") else None
        ),
        "roe_pct": (
            _safe(round(fi["returnOnEquity"] * 100, 2)) if fi.get("returnOnEquity") else None
        ),
        "target_mean_price": _safe(fi.get("targetMeanPrice")),
    }

    news = json.loads(stock_news(symbol, 8)).get("news", [])

    return json.dumps(
        {
            "symbol": symbol,
            "reports": {
                "fundamentals": {
                    "data": fund,
                    "snapshot_ts": datetime.utcnow().isoformat(),
                    "source": "Yahoo Finance (yfinance)",
                },
                "technical": {
                    "data": tech,
                    "snapshot_ts": datetime.utcnow().isoformat(),
                    "source": "Yahoo Finance (yfinance)",
                },
                "sentiment": {
                    "data": {"recent_headlines": news},
                    "note": "headlines only; judge tone from the titles",
                    "snapshot_ts": datetime.utcnow().isoformat(),
                    "source": "Yahoo Finance (yfinance)",
                },
            },
            "disclaimer": "Educational analysis only — not financial advice.",
        }
    )