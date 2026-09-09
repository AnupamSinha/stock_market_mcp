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

import pandas as pd
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
ALPHA_VANTAGE_BASE_URL = os.environ.get("ALPHA_VANTAGE_BASE_URL", "https://www.alphavantage.co/query")
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.environ.get("MONGODB_DB_NAME", "stock_data")
JOURNAL_COLLECTION = "decision_journal"

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
def search_symbol(query: str, limit: int = 8) -> str:
    """Resolve a company name or partial symbol to tradeable symbols (e.g. 'reliance' -> RELIANCE.NS). India-first: NSE (.NS) results are ranked before BSE (.BO) and others."""
    try:
        from yfinance import Search
        s = Search(query, max_results=25)
        hits = []
        for r in (s.quotes or []):
            sym = r.get("symbol", "")
            if not sym:
                continue
            hits.append({
                "symbol": sym,
                "name": r.get("shortname") or r.get("longname") or r.get("displayname"),
                "exchange": r.get("exchDisp") or r.get("exchange"),
                "type": r.get("quoteType"),
            })
        # India-first ranking: NSE before BSE before the rest
        def rank(h):
            if h["symbol"].endswith(".NS"):
                return (0, h["symbol"])
            if h["symbol"].endswith(".BO"):
                return (1, h["symbol"])
            return (2, h["symbol"])
        hits.sort(key=rank)
        if not hits:  # fallback: maybe the query IS a symbol — validate directly
            q = query.strip().upper()
            for cand in (q if "." in q else None, f"{q}.NS", f"{q}.BO"):
                if not cand:
                    continue
                try:
                    fi = yf.Ticker(cand).fast_info
                    if _safe(fi.last_price) is not None:
                        hits.append({"symbol": cand, "name": None,
                                     "exchange": "NSE" if cand.endswith(".NS") else "BSE",
                                     "type": None})
                        break
                except Exception:
                    continue
        return json.dumps({"query": query, "results": hits[:limit],
                           "source": "Yahoo Finance (yfinance) Search"})
    except Exception as e:
        return json.dumps({"query": query, "error": str(e)})

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
            "data_snapshot": {
                # every value the score above is computed from — audit trail
                "as_of": h.index[-1].date().isoformat(),
                "generated_at": datetime.utcnow().isoformat(),
                "sma50": _safe(round(float(sma50), 2)) if sma50 is not None else None,
                "sma200": _safe(round(float(sma200), 2)) if sma200 is not None else None,
                "rsi_14": _safe(round(rsi, 1)),
                "macd": _safe(round(float(macd.iloc[-1]), 3)),
                "macd_signal": _safe(round(float(sig.iloc[-1]), 3)),
                "return_6m_pct": _safe(round(ret_6m, 1)),
                "source": "Yahoo Finance (yfinance), daily OHLC adjusted",
            },
            "fundamentals": {
                "pe_ratio": _safe(pe), "forward_pe": _safe(fi.get("forwardPE")),
                "market_cap": _safe(fi.get("marketCap")),
                "dividend_yield_pct": _safe(round(fi["dividendYield"], 2)) if fi.get("dividendYield") else None,
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
                    "dividend_yield_pct": _safe(round(fi["dividendYield"], 2)) if fi.get("dividendYield") else None,
                    "return_1y_pct": ret_1y})
    return json.dumps({"comparison": out, "source": "Yahoo Finance (yfinance)"})

# ---------------------------------------------------------------- movers cache
_MOVERS_CACHE = {"ts": 0.0, "data": None}
_NSE_MOVERS_CACHE = {"ts": 0.0, "data": None}
_MOVERS_TTL = 600  # seconds — bsedata scrapes BSE pages; cache hard to stay polite

def _bse_movers():
    """Top BSE gainers/losers via bsedata with a TTL cache. Raises on failure."""
    import time as _time
    now = _time.time()
    if _MOVERS_CACHE["data"] is not None and now - _MOVERS_CACHE["ts"] < _MOVERS_TTL:
        return {**_MOVERS_CACHE["data"], "cached": True}
    from bsedata.bse import BSE
    b = BSE()
    def _rows(rows):
        return [{"symbol": f"{r['scripCode']}.BO", "company": r.get("securityID"),
                 "price": _safe(r.get("LTP")), "change_pct": _safe(r.get("pChange"))}
                for r in rows[:5]]
    data = {"gainers": _rows(b.topGainers()), "losers": _rows(b.topLosers()),
            "cached": False}
    _MOVERS_CACHE.update(ts=now, data=data)
    return data

def _nse_movers():
    """Top NSE gainers/losers from nseindia.com's public endpoint with a TTL cache. Raises on failure."""
    import time as _time
    import requests
    now = _time.time()
    if _NSE_MOVERS_CACHE["data"] is not None and now - _NSE_MOVERS_CACHE["ts"] < _MOVERS_TTL:
        return {**_NSE_MOVERS_CACHE["data"], "cached": True}
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                      "Accept": "*/*", "Referer": "https://www.nseindia.com/"})
    s.get("https://www.nseindia.com", timeout=10)  # cookie bootstrap
    def _rows(url):
        d = s.get(url, timeout=10).json()
        rows = d.get("NIFTY", {}).get("data") if isinstance(d.get("NIFTY"), dict) else None
        if rows is None:  # losers endpoint nests differently: top-level "data"
            rows = d.get("data", [])
        return [{"symbol": f"{r['symbol']}.NS", "company": r.get("symbol"),
                 "price": _safe(r.get("ltp")), "change_pct": _safe(r.get("perChange"))}
                for r in rows[:5]]
    data = {"gainers": _rows("https://www.nseindia.com/api/live-analysis-variations?index=gainers"),
            # yes, "loosers" — NSE's own typo, the correct spelling returns an error
            "losers": _rows("https://www.nseindia.com/api/live-analysis-variations?index=loosers"),
            "cached": False}
    _NSE_MOVERS_CACHE.update(ts=now, data=data)
    return data

@mcp.tool()
def market_movers(market: str = "india") -> str:
    """Market snapshot + top movers. market: 'india' (BSE top gainers/losers via bsedata, NIFTY index via Yahoo) or 'us' (S&P 500 index)."""
    index_symbol = "^NSEI" if market.lower() == "india" else "^GSPC"
    index_name = "NIFTY 50" if market.lower() == "india" else "S&P 500"
    out = {"market": market, "index": index_name,
           "source": "Yahoo Finance (yfinance)"}
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
            out["note"] = "BSE movers unavailable — pass candidate symbols to analyze_watchlist instead."
    else:
        out["suggested_workflow"] = "run analyze_watchlist on your candidate symbols"
    return json.dumps(out)

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

# ---------------------------------------------------------------- decision journal
_JOURNAL_FALLBACK = os.path.join(os.path.dirname(__file__), "decision_journal.json")

def _journal_collection():
    """MongoDB collection for the decision journal, or None to use the JSON fallback."""
    try:
        import pymongo
        client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[MONGODB_DB][JOURNAL_COLLECTION]
    except Exception:
        return None

def _journal_insert(doc: dict):
    doc = {"_ts": datetime.utcnow().isoformat(), **doc}
    col = _journal_collection()
    if col is not None:
        col.insert_one(doc)
        doc.pop("_id", None)
    else:  # fallback: append to a local JSON file
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
    """Record a BUY/HOLD/SELL decision in the journal (MongoDB, JSON-file fallback) with the price at decision time."""
    action = action.upper()
    if action not in ("BUY", "HOLD", "SELL"):
        return json.dumps({"error": "action must be BUY, HOLD or SELL"})
    try:
        price = _safe(yf.Ticker(symbol).fast_info.last_price)
    except Exception:
        price = None
    doc = _journal_insert({"kind": "decision", "symbol": symbol, "action": action,
                           "rationale": rationale, "score": score, "price_at_decision": price,
                           "status": "open"})
    return json.dumps({"logged": True, "decision": doc})

@mcp.tool()
def review_decisions(symbol: str = "") -> str:
    """Review logged decisions against current prices: return since decision, whether the call was right, and a reflection prompt."""
    query = {"kind": "decision"} | ({"symbol": symbol} if symbol else {})
    docs = [d for d in _journal_find(query) if d.get("status") == "open"]
    if not docs:
        return json.dumps({"review": [], "note": "no open decisions logged yet — use log_decision"})
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
                    entry["outcome"] = "CORRECT" if ret > 1 else ("WRONG" if ret < -1 else "NEUTRAL")
                elif d["action"] == "SELL":
                    entry["outcome"] = "CORRECT" if ret < -1 else ("WRONG" if ret > 1 else "NEUTRAL")
                else:
                    entry["outcome"] = "NEUTRAL" if abs(ret) <= 5 else "BROKEN (price moved >5%)"
        except Exception as e:
            entry["error"] = str(e)
        review.append(entry)
    return json.dumps({"review": review, "n_open": len(docs),
                       "disclaimer": "Educational analysis only — not financial advice."})

@mcp.tool()
def analyst_reports(symbol: str) -> str:
    """Three separate analyst reports for one symbol (fundamentals / technical / news sentiment), each grounded in a timestamped data snapshot — the input for a bull-vs-bear debate."""
    # technical report
    tech = json.loads(technical_analysis(symbol, "1y"))
    # fundamentals report
    t = yf.Ticker(symbol)
    fi = t.info or {}
    fund = {"name": fi.get("shortName", symbol), "sector": fi.get("sector", "N/A"),
            "pe_ratio": _safe(fi.get("trailingPE")), "forward_pe": _safe(fi.get("forwardPE")),
            "market_cap": _safe(fi.get("marketCap")),
            "dividend_yield_pct": _safe(round(fi["dividendYield"], 2)) if fi.get("dividendYield") else None,
            "debt_to_equity": _safe(fi.get("debtToEquity")),
            "profit_margin_pct": _safe(round(fi["profitMargins"] * 100, 2)) if fi.get("profitMargins") else None,
            "roe_pct": _safe(round(fi["returnOnEquity"] * 100, 2)) if fi.get("returnOnEquity") else None,
            "target_mean_price": _safe(fi.get("targetMeanPrice"))}
    # sentiment report: headlines only (no NLP — the client LLM judges tone)
    news = json.loads(stock_news(symbol, 8)).get("news", [])
    return json.dumps({
        "symbol": symbol,
        "reports": {
            "fundamentals": {"data": fund, "snapshot_ts": datetime.utcnow().isoformat(), "source": "Yahoo Finance (yfinance)"},
            "technical": {"data": tech, "snapshot_ts": datetime.utcnow().isoformat(), "source": "Yahoo Finance (yfinance)"},
            "sentiment": {"data": {"recent_headlines": news},
                          "note": "headlines only; judge tone from the titles",
                          "snapshot_ts": datetime.utcnow().isoformat(), "source": "Yahoo Finance (yfinance)"},
        },
        "disclaimer": "Educational analysis only — not financial advice.",
    })

@mcp.tool()
def earnings_calendar(symbol: str) -> str:
    """Upcoming earnings dates, EPS estimates, and time until earnings announcement for a symbol. Returns recent earnings history if no upcoming date is scheduled."""
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        out = {
            "symbol": symbol,
            "source": "Yahoo Finance (yfinance)",
        }
        
        # Try earnings_dates first (most reliable for upcoming)
        earnings_dates = t.earnings_dates
        if earnings_dates is not None:
            try:
                df = earnings_dates
                if not df.empty:
                    # First row is the next upcoming earnings (index contains the date)
                    first_idx = df.index[0]
                    next_row = df.iloc[0]
                    eps_est = next_row.get("EPS Estimate")
                    eps_rep = next_row.get("Reported EPS")
                    
                    # Date is in the index, not a column
                    ed_str = str(first_idx)[:10]
                    # Check if this is a future date (Reported EPS not available = upcoming)
                    if pd.isna(eps_rep):
                        out["next_earnings_date"] = ed_str
                        out["eps_estimate"] = _safe(eps_est)
                        # Calculate days until
                        try:
                            ed_date = first_idx.date() if hasattr(first_idx, "date") else datetime.strptime(ed_str, "%Y-%m-%d").date()
                            now = datetime.now().date()
                            delta = (ed_date - now).days
                            out["days_until"] = delta
                            out["time_until"] = f"{delta} days" if delta > 0 else "today"
                        except Exception:
                            pass
                    
                    # Recent earnings history (past quarters only)
                    recent = []
                    for i, (idx, row) in enumerate(df.iterrows()):
                        if i == 0 and pd.isna(row.get("Reported EPS")):
                            continue  # skip the upcoming one, already handled
                        if i >= 5:  # Up to 4 past quarters
                            break
                        if pd.notna(row.get("Reported EPS")):
                            recent.append({
                                "period": str(idx)[:10],
                                "eps_estimate": _safe(row.get("EPS Estimate")),
                                "eps_reported": _safe(row.get("Reported EPS")),
                                "surprise_pct": _safe(row.get("Surprise(%)"))
                            })
                    if recent:
                        out["recent_earnings"] = recent
            except Exception as e:
                out["parse_error"] = str(e)
        
        # Fallback: quarterly financials for EPS
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
        
        # Guidance and fundamentals from info
        out["eps_estimate"] = out.get("eps_estimate") or _safe(info.get("epsEstimate"))
        out["earnings_high"] = _safe(info.get("earningsHigh"))
        out["earnings_low"] = _safe(info.get("earningsLow"))
        out["revenue_growth"] = _safe(round(info.get("revenueGrowth", 0) * 100, 2)) if info.get("revenueGrowth") else None
        
        # Note if no upcoming date
        if not out.get("next_earnings_date"):
            out["note"] = "No scheduled earnings date found — check recent_earnings for last 4 quarters."
        
        return json.dumps(out)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})

@mcp.tool()
def stock_screener(symbols: str = "", min_pe: float = None, max_pe: float = None, 
                   min_rsi: float = None, max_rsi: float = None,
                   min_dividend_yield: float = None, min_roe: float = None,
                   min_score: int = None) -> str:
    """Screen stocks by criteria: P/E, RSI, dividend yield, ROE, or analyze_stock score. Returns matching symbols that pass all filters. Symbols: comma-separated (default: default watchlist)."""
    syms = [s.strip() for s in symbols.split(",") if s.strip()] or DEFAULT_WATCHLIST.split(",")
    matches = []
    
    for s in syms[:20]:  # limit to 20 for performance
        try:
            # Get fundamentals and technicals in parallel
            t = yf.Ticker(s)
            info = t.info or {}
            h = _history(s, "6mo")
            
            if h.empty:
                continue
                
            # Calculate RSI
            close = h["Close"]
            rsi = float(_rsi(close).iloc[-1]) if len(close) >= 14 else None
            
            # Get fundamentals
            pe = info.get("trailingPE")
            dividend_yield = info.get("dividendYield")
            roe = info.get("returnOnEquity")
            
            # Get analyze_stock score (replicate logic)
            score = 50.0
            sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
            if sma50 is not None and float(close.iloc[-1]) > sma50:
                score += 10
            else:
                score -= 10
            if rsi is not None:
                if rsi < 30:
                    score += 10
                elif rsi > 70:
                    score -= 10
                else:
                    score += 2  # neutral but not bearish
            macd, sig = _macd(close)
            if macd.iloc[-1] > sig.iloc[-1]:
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
            if min_rsi is not None and (rsi is None or rsi < min_rsi):
                continue
            if max_rsi is not None and (rsi is None or rsi > max_rsi):
                continue
            if min_dividend_yield is not None and (dividend_yield is None or dividend_yield * 100 < min_dividend_yield):
                continue
            if min_roe is not None and (roe is None or roe * 100 < min_roe):
                continue
            if min_score is not None and score < min_score:
                continue
            
            matches.append({
                "symbol": s,
                "name": info.get("shortName", s),
                "price": _safe(round(float(close.iloc[-1]), 2)),
                "pe_ratio": _safe(pe),
                "rsi_14": _safe(round(rsi, 1)) if rsi else None,
                "dividend_yield_pct": _safe(round(dividend_yield * 100, 2)) if dividend_yield else None,
                "roe_pct": _safe(round(roe * 100, 2)) if roe else None,
                "score": _safe(round(score, 1)),
                "recommendation": _score_to_action(score)
            })
        except Exception:
            continue
    
    return json.dumps({
        "matches": matches,
        "n_input": len(syms),
        "n_matches": len(matches),
        "filters_applied": {
            "min_pe": min_pe, "max_pe": max_pe,
            "min_rsi": min_rsi, "max_rsi": max_rsi,
            "min_dividend_yield": min_dividend_yield,
            "min_roe": min_roe, "min_score": min_score
        },
        "source": "Yahoo Finance (yfinance)"
    })

@mcp.tool()
def correlation_analysis(symbol: str, benchmark: str = "^NSEI", period: str = "1y") -> str:
    """Calculate correlation between a stock and a benchmark (^NSEI for NIFTY 50, ^GSPC for S&P 500). Returns correlation coefficient, rolling correlation, and beta."""
    try:
        stock = yf.Ticker(symbol)
        bench = yf.Ticker(benchmark)
        
        stock_h = stock.history(period=period, auto_adjust=True)
        bench_h = bench.history(period=period, auto_adjust=True)
        
        if stock_h.empty or bench_h.empty:
            return json.dumps({"error": "No price data available"})
        
        # Align dates
        aligned = stock_h["Close"].align(bench_h["Close"], join="inner")
        stock_returns = aligned[0].pct_change().dropna()
        bench_returns = aligned[1].pct_change().dropna()
        
        # Correlation
        corr = stock_returns.corr(bench_returns)
        
        # Rolling correlation (30-day windows)
        rolling_corr = stock_returns.rolling(30).corr(bench_returns)
        rolling_corr_series = rolling_corr.dropna()
        
        # Beta (covariance / variance)
        beta = stock_returns.cov(bench_returns) / bench_returns.var()
        
        # R-squared
        r_squared = corr ** 2
        
        return json.dumps({
            "symbol": symbol,
            "benchmark": benchmark,
            "correlation": _safe(round(corr, 3)),
            "beta": _safe(round(beta, 3)),
            "r_squared": _safe(round(r_squared, 3)),
            "correlation_trend": "high" if abs(corr) > 0.7 else ("moderate" if abs(corr) > 0.4 else "low"),
            "rolling_correlation_30d": {
                "current": _safe(round(rolling_corr_series.iloc[-1], 3)),
                "mean": _safe(round(rolling_corr_series.mean(), 3)),
                "min": _safe(round(rolling_corr_series.min(), 3)),
                "max": _safe(round(rolling_corr_series.max(), 3)),
            },
            "period_days": len(stock_returns),
            "source": "Yahoo Finance (yfinance)"
        })
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})

@mcp.tool()
def currency_impact(symbol: str) -> str:
    """Show returns in both INR and USD to understand currency impact. Useful for NRIs or foreign investors tracking Indian stocks."""
    try:
        t = yf.Ticker(symbol)
        h = t.history(period="1y", auto_adjust=True)
        
        if h.empty:
            return json.dumps({"symbol": symbol, "error": "No price data"})
        
        # Get USD/INR rate
        inr = yf.Ticker("INR=X")
        inr_h = inr.history(period="1y", interval="1d")
        
        # Align stock and currency dates
        stock_close = h["Close"]
        if not inr_h.empty:
            # Get most recent USD/INR
            usd_inr = inr_h["Close"].iloc[-1]
            # Get USD/INR from 1 year ago
            if len(inr_h) > 250:
                usd_inr_start = inr_h["Close"].iloc[-250]
            else:
                usd_inr_start = inr_h["Close"].iloc[0]
        else:
            usd_inr = 83.0  # fallback
            usd_inr_start = 83.0
        
        # Calculate returns
        price_start = float(stock_close.iloc[0])
        price_end = float(stock_close.iloc[-1])
        
        inr_return = (price_end / price_start - 1) * 100
        
        # USD return = (Price_END / Price_START) * (USD_INR_START / USD_INR_END) - 1
        usd_return = (price_end / price_start) * (usd_inr_start / usd_inr) - 1
        usd_return_pct = usd_return * 100
        
        # Currency impact
        currency_impact_pct = usd_return_pct - inr_return
        
        return json.dumps({
            "symbol": symbol,
            "period": "1y",
            "inr": {
                "price_start": _safe(round(price_start, 2)),
                "price_end": _safe(round(price_end, 2)),
                "return_pct": _safe(round(inr_return, 2))
            },
            "usd": {
                "usd_inr_start": _safe(round(usd_inr_start, 2)),
                "usd_inr_end": _safe(round(usd_inr, 2)),
                "return_pct": _safe(round(usd_return_pct, 2))
            },
            "currency_impact_pct": _safe(round(currency_impact_pct, 2)),
            "interpretation": "rupee weakened" if currency_impact_pct > 0 else "rupee strengthened",
            "source": "Yahoo Finance (yfinance)"
        })
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})

@mcp.tool()
def dividend_calendar(symbol: str) -> str:
    """Upcoming dividend dates, ex-dividend dates, yield, and payment history. For Indian and US stocks."""
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        out = {"symbol": symbol, "source": "Yahoo Finance (yfinance)"}
        
        # Current dividend info
        out["dividend_yield"] = _safe(round(info.get("dividendYield", 0) * 100, 2)) if info.get("dividendYield") else None
        out["dividend_per_share"] = _safe(info.get("dividendRate"))
        out["payout_ratio"] = _safe(round(info.get("payoutRatio", 0) * 100, 2)) if info.get("payoutRatio") else None
        out["ex_dividend_date"] = str(info.get("exDividendDate"))[:10] if info.get("exDividendDate") else None
        
        # Dividend history from splits/v_actions (limited to last 5)
        try:
            actions = t.actions
            if actions is not None and not actions.empty:
                dividends = actions[actions["Dividends"] > 0].tail(5)
                if not dividends.empty:
                    out["recent_dividends"] = [
                        {
                            "date": str(idx)[:10],
                            "amount": _safe(row["Dividends"]),
                            "type": "regular"
                        }
                        for idx, row in dividends.iterrows()
                    ]
        except Exception:
            pass
        
        # If no action data, try getting fromSplits
        if "recent_dividends" not in out:
            try:
                from yfinance import shared
                import pandas as pd
                # Try to get from info
                div_history = info.get(" dividendHistory")
                if div_history:
                    out["recent_dividends"] = div_history
            except Exception:
                pass
        
        # Fallback: use annual dividend rate and frequency
        out["annual_dividend_rate"] = _safe(info.get("dividendRate"))
        out["frequency"] = info.get("dividendFrequency", "quarterly") if info.get("dividendRate") else None
        
        if not out.get("recent_dividends"):
            out["note"] = "Limited dividend history available — dividend_yield and annual_dividend_rate show current info."
        
        return json.dumps(out)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})

@mcp.tool()
def options_data(symbol: str) -> str:
    """Options chain data: implied volatility, put/call ratios, strike prices, expiration dates. For US stocks with options chains."""
    try:
        t = yf.Ticker(symbol)
        
        # Check if options exist
        if not t.options:
            return json.dumps({"symbol": symbol, "error": "No options data available — symbol may not have options"})
        
        # Get first expiration's chain (default behavior)
        opt = t.option_chain(t.options[0])
        
        calls = opt.calls
        puts = opt.puts
        
        # Basic metrics
        out = {"symbol": symbol, "source": "Yahoo Finance (yfinance)"}
        
        # Current stock price
        try:
            out["current_price"] = _safe(round(float(t.fast_info.last_price), 2))
        except Exception:
            pass
        
        # Expiration dates
        out["expiration_dates"] = [str(d)[:10] for d in t.options] if t.options else []
        
        if not calls.empty:
            # IV - weighted average from near-the-money calls
            atm_mask = (calls["strike"] >= out.get("current_price", 0) * 0.95) & (calls["strike"] <= out.get("current_price", float('inf')) * 1.05)
            atm_calls = calls[atm_mask]
            if not atm_calls.empty:
                out["implied_volatility_call"] = _safe(round(atm_calls["impliedVolatility"].mean() * 100, 2))
            else:
                out["implied_volatility_call"] = _safe(round(calls["impliedVolatility"].mean() * 100, 2))
        
        if not puts.empty:
            # IV from puts
            atm_mask = (puts["strike"] >= out.get("current_price", 0) * 0.95) & (puts["strike"] <= out.get("current_price", float('inf')) * 1.05)
            atm_puts = puts[atm_mask]
            if not atm_puts.empty:
                out["implied_volatility_put"] = _safe(round(atm_puts["impliedVolatility"].mean() * 100, 2))
            else:
                out["implied_volatility_put"] = _safe(round(puts["impliedVolatility"].mean() * 100, 2))
        
        # Put/Call ratio (volume or open interest)
        if not calls.empty and not puts.empty:
            call_vol = calls["volume"].sum()
            put_vol = puts["volume"].sum()
            call_oi = calls["openInterest"].sum()
            put_oi = puts["openInterest"].sum()
            
            out["put_call_volume_ratio"] = _safe(round(put_vol / call_vol, 3)) if call_vol > 0 else None
            out["put_call_oi_ratio"] = _safe(round(put_oi / call_oi, 3)) if call_oi > 0 else None
            
            # Interpretation
            if out.get("put_call_oi_ratio") and out["put_call_oi_ratio"] > 1:
                out["sentiment"] = "bearish (high put demand)"
            elif out.get("put_call_oi_ratio") and out["put_call_oi_ratio"] < 0.7:
                out["sentiment"] = "bullish (high call demand)"
            else:
                out["sentiment"] = "neutral"
        
        # Near-the-money options (useful for quick view)
        if not calls.empty and not puts.empty:
            price = out.get("current_price", 0)
            if price:
                call_strikes = calls[(calls["strike"] >= price * 0.95) & (calls["strike"] <= price * 1.05)]
                put_strikes = puts[(puts["strike"] >= price * 0.95) & (puts["strike"] <= price * 1.05)]
                
                out["atm_calls"] = [{"strike": _safe(row["strike"]), "bid": _safe(row["bid"]), "ask": _safe(row["ask"]), "iv": _safe(round(row["impliedVolatility"] * 100, 2))}
                                   for _, row in call_strikes.head(3).iterrows()]
                out["atm_puts"] = [{"strike": _safe(row["strike"]), "bid": _safe(row["bid"]), "ask": _safe(row["ask"]), "iv": _safe(round(row["impliedVolatility"] * 100, 2))}
                                  for _, row in put_strikes.head(3).iterrows()]
        
        # Risk assessment
        if out.get("implied_volatility_call"):
            if out["implied_volatility_call"] > 50:
                out["iv_percentile"] = "high"
                out["risk_note"] = "Options pricing suggests elevated uncertainty"
            elif out["implied_volatility_call"] < 20:
                out["iv_percentile"] = "low"
                out["risk_note"] = "Options pricing suggests calm market"
            else:
                out["iv_percentile"] = "moderate"
        
        return json.dumps(out)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})

@mcp.tool()
def sector_mapping(symbol: str) -> str:
    """Get sector, industry, and peer tickers for a stock. Useful for peer comparison and sector analysis."""
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        
        out = {
            "symbol": symbol,
            "source": "Yahoo Finance (yfinance)"
        }
        
        # Sector and industry
        out["sector"] = info.get("sector")
        out["industry"] = info.get("industry")
        out["industry_key"] = info.get("industryKey")
        
        # Company info
        out["name"] = info.get("shortName")
        out["full_time_employees"] = info.get("fullTimeEmployees")
        out["business_summary"] = info.get("businessSummary", "")[:500] if info.get("businessSummary") else None
        
        # Peer tickers (Yahoo provides a peer list)
        out["peers"] = info.get("peers") or []
        
        # Market data
        out["market_cap"] = _safe(info.get("marketCap"))
        out["exchange"] = info.get("exchange")
        out["quote_type"] = info.get("quoteType")
        
        # Key metrics for sector context
        out["trailing_pe"] = _safe(info.get("trailingPE"))
        out["forward_pe"] = _safe(info.get("forwardPE"))
        out["profit_margin"] = _safe(round(info.get("profitMargins", 0) * 100, 2)) if info.get("profitMargins") else None
        out["roe"] = _safe(round(info.get("returnOnEquity", 0) * 100, 2)) if info.get("returnOnEquity") else None
        out["beta"] = _safe(info.get("beta"))
        
        return json.dumps(out)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})

@mcp.tool()
def fii_dii_flows(symbol: str = "", period: str = "1m") -> str:
    """India: Institutional holder data for stocks. Returns institutional ownership, recent changes for FII (Foreign Institutional Investors) and DII (Domestic Institutional Investors). For Indian stocks via yfinance institutional holders."""
    try:
        t = yf.Ticker(symbol) if symbol else None
        out = {
            "period": period,
            "source": "Yahoo Finance (yfinance)"
        }
        
        if symbol:
            # Per-stock institutional holders
            holders = t.institutional_holders if hasattr(t, 'institutional_holders') else None
            
            if holders is not None and not holders.empty:
                out["institutional_holders"] = [
                    {
                        "holder": row.get("Holder", str(row.get("name", ""))),
                        "shares": _safe(row.get("Shares")),
                        "value": _safe(row.get("Value")),
                        "pct_held": _safe(round(row.get("pctOfShares", 0) * 100, 2)) if row.get("pctOfShares") else None,
                        "change_pct": _safe(round(row.get("Change", 0) * 100, 2)) if row.get("Change") else None
                    }
                    for _, row in holders.iterrows()
                ]
            
            # Mutual fund holders (DII proxy for India)
            mfh = t.mutualfund_holders if hasattr(t, 'mutualfund_holders') else None
            if mfh is not None and not mfh.empty:
                out["mutual_fund_holders"] = [
                    {
                        "holder": row.get("Holder", str(row.get("name", ""))),
                        "shares": _safe(row.get("Shares")),
                        "value": _safe(row.get("Value")),
                        "pct_held": _safe(round(row.get("pctOfShares", 0) * 100, 2)) if row.get("pctOfShares") else None,
                    }
                    for _, row in mfh.head(10).iterrows()
                ]
            
            # Insider transactions
            insider = t.insider_transactions if hasattr(t, 'insider_transactions') else None
            if insider is not None and not insider.empty:
                try:
                    recent = insider[insider["Date"] > (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")]
                    out["insider_activity"] = [
                        {
                            "date": str(row.get("Date"))[:10] if row.get("Date") else None,
                            "type": row.get("Transaction"),
                            "shares": _safe(row.get("Shares")),
                            "value": _safe(row.get("Value")),
                        }
                        for _, row in recent.head(5).iterrows()
                    ]
                except Exception:
                    # Fallback: just take last 5 transactions
                    out["insider_activity"] = [
                        {
                            "date": str(row.get("Date"))[:10] if row.get("Date") else None,
                            "type": row.get("Transaction"),
                            "shares": _safe(row.get("Shares")),
                            "value": _safe(row.get("Value")),
                        }
                        for _, row in insider.head(5).iterrows()
                    ]
            
            if not out.get("institutional_holders"):
                out["note"] = "Limited institutional holder data available for this symbol"
        else:
            # Market-level: Note about FII/DII
            out["note"] = "Market-wide FII/DII flows require paid NSE API. For stock-specific institutional holders, provide a symbol."
            out["alternative"] = "Use sector_mapping + compare_stocks for sector-level analysis"
        
        return json.dumps(out)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})


@mcp.prompt()
def bull_bear_debate(symbol: str) -> str:
    """Structured bull-vs-bear debate workflow for a stock (TradingAgents-style, India-focused)."""
    return f"""You are conducting a structured investment debate for {symbol} (NSE/BSE). Follow these steps:

1. GATHER: Call the analyst_reports tool for {symbol}. Treat every number in the reports as verified data — do not use figures from memory.
2. BULL CASE: Argue the strongest honest case FOR the stock, citing only the snapshot data (and further tool calls if needed).
3. BEAR CASE: Argue the strongest honest case AGAINST it, same grounding rules. Steelman both sides.
4. RISK CHECK: List what would falsify the bull case, what would falsify the bear case, position-size and liquidity considerations for an NSE/BSE large-cap, and upcoming events (earnings, ex-dividend) that change the risk.
5. DECISION: Give BUY/HOLD/SELL with a 0-100 score and a confidence level (low/medium/high), stating the time horizon the call is valid for.
6. JOURNAL: Call log_decision with the final action, score, and a one-paragraph rationale.

Rules: every claim must trace to the data snapshot or a fresh tool call. If data is missing, say so instead of filling gaps from memory. This is educational analysis, not financial advice — say so in the final answer."""



# ---------------------------------------------------------------- main
if __name__ == "__main__":
    mcp.run()  # stdio transport
