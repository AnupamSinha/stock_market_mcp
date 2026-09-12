# 🧠 stock_market_mcp

> **FoodForBrains** · *Feeding your brain the data it needs to decide.*

A Model Context Protocol (MCP) server that analyzes stocks and returns a scored **BUY / HOLD / SELL** assessment, so you can ask your AI client "which stocks should I look at?" and get data-backed answers.

Works for the **Indian market** (NSE/BSE) and **US market** out of the box.

📖 **Full documentation:** the [wiki](https://github.com/AnupamSinha/stock_market_mcp/wiki) — setup, tools reference, architecture, backtesting and FAQ.

## APIs used

| API | Purpose | Key needed? |
|---|---|---|
| **Yahoo Finance** (via [`yfinance`](https://pypi.org/project/yfinance/)) | Quotes, price history, fundamentals, news — the primary data source for all analysis tools | No (free) |
| **bsedata** | BSE top gainers/losers in `market_movers` | No (scrapes bseindia.com; 10-min TTL cache, graceful fallback if BSE blocks) |
| **nseindia.com public API** | NSE top gainers/losers in `market_movers` | No (unofficial; 10-min TTL cache, graceful fallback if NSE blocks) |
| **Alpha Vantage** (optional) | Extra company-overview data (`alpha_vantage_overview` tool) | Yes — free key at https://www.alphavantage.co/support/#api-key |

> **Alpha Vantage free-tier notes (verified live):** the free key is rate-limited to **~25 requests/day, 1 request/sec** — exceeding it returns an "Information" notice instead of data. Also, Alpha Vantage's `OVERVIEW` endpoint works for **US symbols** (e.g. `AAPL` ✔) but returns empty data for NSE/BSE symbols (`RELIANCE.BSE` ✘) — Indian-market coverage comes entirely from Yahoo Finance, which is why Yahoo is the primary source.

## Tools

| Tool | What it does |
|---|---|
| `get_quote` | Current price + day change for a symbol |
| `search_symbol` | Resolve a company name to symbols (e.g. "reliance" → RELIANCE.NS); India-first ranking |
| `technical_analysis` | SMA 20/50/200, RSI-14, MACD + signal, 52-week range, daily volatility |
| `analyze_stock` | Full technical + fundamental analysis → 0–100 score, BUY/HOLD/SELL, with reasons |
| `analyze_watchlist` | Analyze & rank up to 15 symbols (defaults to NSE large caps) |
| `compare_stocks` | Side-by-side P/E, margins, ROE, debt/equity, dividend yield, 1-year return |
| `market_movers` | Index + **real top gainers/losers for both exchanges**: NSE via nseindia.com API, BSE via `bsedata` (10-min caches), NIFTY/S&P index via Yahoo |
| `stock_news` | Recent news headlines for a symbol |
| `alpha_vantage_overview` | Optional Alpha Vantage company overview (needs API key) |
| `log_decision` | Record a BUY/HOLD/SELL decision + rationale + price in the decision journal |
| `review_decisions` | Review logged decisions vs current prices (return since, outcome verdict) |
| `analyst_reports` | Three separate grounded reports (fundamentals / technical / sentiment) for one symbol |

### Prompts

| Prompt | What it does |
|---|---|
| `bull_bear_debate` | TradingAgents-style structured workflow: gather grounded reports → bull case → bear case → risk check → decision → log it. (Inspired by [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents), adapted for NSE/BSE.) |

### Decision journal

Every `log_decision` call is stored in **MongoDB** (`stock_data.decision_journal`, configurable via `MONGODB_URI`/`MONGODB_DB_NAME`). If MongoDB is unreachable, the journal automatically falls back to a local `decision_journal.json`. `review_decisions` closes the loop: it prices each open decision and marks the outcome CORRECT / WRONG / NEUTRAL — so recommendations are measured, not forgotten.

### Grounded data snapshots

`analyze_stock` and `analyst_reports` embed a timestamped `data_snapshot` — every indicator value the score is computed from, with its source. Follows the TradingAgents principle that analysis claims must trace to a verified data snapshot, never LLM memory.

### Symbol formats

| Market | Format | Example |
|---|---|---|
| NSE (India) | `<SYMBOL>.NS` | `RELIANCE.NS`, `TCS.NS` |
| BSE (India) | `<CODE>.BO` | `500325.BO` |
| US | plain ticker | `AAPL`, `MSFT` |

## Setup

### Prerequisites

- **Python 3.10+** (tested on 3.13)
- **pip**
- An MCP client (ZCode, Claude Desktop, or any MCP-compatible client)
- (Optional) Alpha Vantage API key

### 1. Get the code

```bash
git clone https://github.com/AnupamSinha/stock_market_mcp.git
cd stock_market_mcp
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

This installs `mcp` (the MCP SDK) and `yfinance`.

> **macOS note:** if HTTPS calls fail with an SSL certificate error, run `pip install certifi`. The server already uses `certifi` automatically when present.

### 3. Configure the Alpha Vantage key (optional)

Create a `.env` file in the project root (or export an env var). The server loads `.env` automatically at startup — existing environment variables take precedence:

```bash
# .env
ALPHA_VANTAGE_API_KEY=your_key_here
ALPHA_VANTAGE_BASE_URL=https://www.alphavantage.co/query
```

| Env var | Default | Description |
|---|---|---|
| `ALPHA_VANTAGE_API_KEY` | *(empty)* | Alpha Vantage key; empty disables only the `alpha_vantage_overview` tool |
| `ALPHA_VANTAGE_BASE_URL` | `https://www.alphavantage.co/query` | Alpha Vantage endpoint |

All other tools work with **no configuration at all**.

## Run

```bash
python3 server.py
```

The server runs on **stdio** — it's not a web server; an MCP client launches it and talks to it over stdin/stdout. You normally don't run it by hand; the client config below does it for you.

## Configure your MCP client

### ZCode

Add to `~/.zcode/cli/config.json` (user scope — available in every workspace):

```json
{
  "mcp": {
    "servers": {
      "stock_market_mcp": {
        "command": "python3",
        "args": ["/absolute/path/to/stock_market_mcp/server.py"]
      }
    }
  }
}
```

Restart ZCode (or start a new session) — the tools appear as `mcp__stock_market_mcp__*` and connect automatically.

### Claude Desktop

Edit the config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "stock_market_mcp": {
      "command": "python3",
      "args": ["/absolute/path/to/stock_market_mcp/server.py"]
    }
  }
}
```

Restart Claude Desktop and start a **new conversation** — the tools icon (hammer) should show the stock tools.

> Use **absolute paths** in both configs. If `python3` isn't found, use the full path (`which python3` to find it).

## Verify it works

Run an end-to-end test with a real MCP client handshake:

```bash
python3 - <<'EOF'
import asyncio, json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python3", args=["server.py"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])
            res = await s.call_tool("analyze_watchlist", {"symbols": "RELIANCE.NS,ITC.NS"})
            print(json.loads(res.content[0].text)["ranked"])

asyncio.run(main())
EOF
```

Expected output: the 8 tool names and a ranked list with scores and recommendations.

## Example prompts (once connected)

- *"Analyze my watchlist and tell me which stocks to consider buying"*
- *"Do a technical analysis of TCS.NS"*
- *"Compare RELIANCE.NS, HDFCBANK.NS and INFY.NS"*
- *"What's the latest news on INFY.NS?"*
- *"Analyze AAPL and MSFT and tell me which looks better"*

## Troubleshooting

| Symptom | Fix |
|---|---|
| Tools don't appear in the client | Start a **new conversation/session**; check the absolute path to `server.py`; check the client's MCP logs |
| `ModuleNotFoundError: No module named 'mcp'` / `'yfinance'` | `pip install -r requirements.txt` — make sure it's the same Python that runs `server.py` |
| SSL / `CERTIFICATE_VERIFY_FAILED` (macOS) | `pip install certifi` (the server picks it up automatically) |
| Alpha Vantage returns an "Information" message | Free-tier rate limit hit (~25 req/day) — wait, or rely on the Yahoo-based tools |
| `alpha_vantage_overview` says the key isn't set | Check `.env` exists next to `server.py`, or export `ALPHA_VANTAGE_API_KEY` |
| Empty result for an NSE symbol from `alpha_vantage_overview` | Known: Alpha Vantage no longer serves Indian fundamentals — use `analyze_stock` instead |
| `yfinance` rate-limited / empty responses | Yahoo throttles bursts; retry after a short pause |

## Project structure

```
stock_market_mcp/
├── server.py                 # Thin entrypoint: imports modules, runs the server
├── app.py                    # Shared FastMCP instance
├── config.py                 # Env/config constants (.env loader)
├── utils/helpers.py          # Shared helpers (_safe, RSI, MACD, Alpha Vantage)
├── tools/                    # Tool modules (one @mcp.tool per function)
│   ├── core.py               # get_quote, search_symbol, technical_analysis, alpha_vantage_overview
│   ├── analysis.py           # analyze_stock, analyze_watchlist, compare_stocks
│   ├── market.py             # market_movers, stock_news, earnings_calendar
│   ├── screening.py          # stock_screener, correlation_analysis
│   ├── fundamentals.py       # currency_impact, dividend_calendar
│   ├── derivatives.py        # options_data
│   ├── classification.py     # sector_mapping
│   ├── flows.py              # fii_dii_flows
│   └── journal.py            # log_decision, review_decisions, analyst_reports
├── prompts/debate.py         # bull_bear_debate prompt
├── backtest.py               # Backtest harness for the scoring rules (5y NSE, monthly)
├── e2e_test.py               # End-to-end MCP test of all tools + prompt
├── requirements.txt          # mcp, yfinance, bsedata
├── .env                      # Optional: ALPHA_VANTAGE_API_KEY (never committed)
├── .zcode/skills/            # SKILL.md — LLM usage guide
├── wiki/                     # Wiki pages (also published to the GitHub wiki)
└── .gitignore
```

## Backtesting

`backtest.py` replays the technical half of the scoring rules over ~5 years of
NIFTY-100 price history, month by month, and measures forward 1/3/6/12-month
returns by score bucket and quintile against the NIFTY 50 benchmark:

```bash
python3 backtest.py
```

Findings so far (see the script header for limitations): the technical score
has modest short-horizon (1–3 month) ranking power; BUY and HOLD levels are
indistinguishable at longer horizons; the SELL cutoff never triggers on the
technical-only score. Treat the scoring weights as tunable, not settled.

## Acknowledgements

The multi-agent workflow shape — grounded analyst reports, bull-vs-bear
debate, risk check, decision journal with outcome review — is inspired by
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
(Apache-2.0), re-implemented here as a lightweight, India-focused (NSE/BSE)
MCP server. Thanks to the TradingAgents team for open-sourcing the ideas.

## About FoodForBrains

FoodForBrains builds tools that make market information digestible — analysis
you can actually reason about, with every number traceable to its source.
This project is part of that mission: grounded data in, transparent reasoning out.

## Disclaimer

All output is **educational analysis generated from public market data** — it is **not financial advice**. The BUY/HOLD/SELL scores are a screening aid based on simple technical and fundamental rules; do your own research and consult a financial advisor before investing.

## License

MIT
