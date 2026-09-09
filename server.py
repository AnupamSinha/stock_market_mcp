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
            out["bse_movers"] = _bse_movers()
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
