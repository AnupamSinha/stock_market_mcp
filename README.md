# 🧠 stock_market_mcp

> **FoodForBrains** · *Feeding your brain the data it needs to decide.*

`stock_market_mcp` is a Model Context Protocol (MCP) server for stock research and screening. It exposes a verified-data layer that gives AI clients grounded market information for NSE/BSE and US equities, with a simple BUY/HOLD/SELL scoring model layered on top.

The server is designed for clients such as ZCode, Claude Desktop, and other MCP-compatible hosts. It keeps the LLM reasoning layer thin and pushes the data retrieval, calculations, and audit trail into the server.

📖 Full docs: the [wiki](https://github.com/AnupamSinha/stock_market_mcp/wiki)

## What it does

- Covers Indian equities (NSE/BSE) and US tickers.
- Exposes 20 MCP tools plus 1 prompt.
- Uses Yahoo Finance as the default data source for quotes, history, fundamentals, and news.
- Adds NSE/BSE market mover data from public exchange endpoints with 10-minute cache handling.
- Supports a MongoDB-backed decision journal with a local JSON fallback.
- Produces auditable `data_snapshot` blocks so recommendation claims can be traced back to data.

## Core facts

| Area | Details |
|---|---|
| Primary data source | Yahoo Finance (`yfinance`) |
| Optional extra data | Alpha Vantage for company overview, only for US tickers |
| Indian market sources | NSE public API + BSE public scraping (`bsedata`) |
| Journal storage | MongoDB (`stock_data.decision_journal`) or local `decision_journal.json` |
| Protocol | MCP over stdio |
| Python | 3.10+ |

## Tool set

### Market and quote tools

- `get_quote` — current price, previous close, change %
- `search_symbol` — resolve company names to symbols with India-first ranking
- `technical_analysis` — SMA 20/50/200, RSI-14, MACD, 52-week range, daily volatility
- `market_movers` — NSE/BSE gainers/losers + index levels
- `stock_news` — recent headlines for one symbol
- `earnings_calendar` — earnings dates, EPS estimates, surprise history

### Analysis tools

- `analyze_stock` — full technical + fundamental score (0–100), BUY/HOLD/SELL, reasons, data snapshot
- `analyze_watchlist` — rank a list of symbols by score
- `compare_stocks` — side-by-side fundamentals for multiple symbols
- `stock_screener` — filter by valuation, RSI, dividend yield, ROE, and score
- `correlation_analysis` — correlation, beta, r-squared against a benchmark

### Fundamental and market context tools

- `currency_impact` — INR vs USD return comparison
- `dividend_calendar` — yield, ex-dividend, historical payouts
- `options_data` — options chain IV, put/call ratios, ATM details
- `sector_mapping` — sector, industry, peers, market cap, key metrics
- `fii_dii_flows` — institutional holders, mutual-fund holders, insider activity where available

### Journal and workflow tools

- `log_decision` — record a BUY/HOLD/SELL call with rationale
- `review_decisions` — score open journal entries against current prices
- `analyst_reports` — generate fundamentals, technical, and sentiment reports for one symbol

### Prompt

- `bull_bear_debate` — TradingAgents-style workflow: gather data → bull case → bear case → risk check → decision → journal it

## Symbol formats

| Market | Format | Example |
|---|---|---|
| NSE (India) | `<SYMBOL>.NS` | `RELIANCE.NS`, `TCS.NS` |
| BSE (India) | `<CODE>.BO` | `500325.BO` |
| US | plain ticker | `AAPL`, `MSFT` |

## Setup

### Prerequisites

- Python 3.10+
- pip
- An MCP client such as ZCode or Claude Desktop
- Optional: Alpha Vantage API key for `alpha_vantage_overview`
- Optional: MongoDB for decision-journal persistence

### Install

```bash
git clone https://github.com/AnupamSinha/stock_market_mcp.git
cd stock_market_mcp
pip install -r requirements.txt
```

### Optional environment config

Create a `.env` file in the project root (or export the same env vars):

```bash
ALPHA_VANTAGE_API_KEY=your_key_here
ALPHA_VANTAGE_BASE_URL=https://www.alphavantage.co/query
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=stock_data
```

If `ALPHA_VANTAGE_API_KEY` is empty, `alpha_vantage_overview` simply reports that the feature is disabled.

> macOS users sometimes hit SSL errors while installing packages. If that happens, run `pip install certifi` and the server will pick it up automatically.

## Run the server

This project runs as an MCP stdio server. The client starts it; you normally do not run it manually unless testing.

```bash
python3 server.py
```

## MCP client configuration

### ZCode

Add this to `~/.zcode/cli/config.json`:

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

### Claude Desktop

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

Use absolute paths. Start a new session after adding the server.

## Verify the connection

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
            prompts = await s.list_prompts()
            print("TOOLS:", [t.name for t in tools.tools])
            print("PROMPTS:", [p.name for p in prompts.prompts])

asyncio.run(main())
EOF
```

Expected result: 20 tool names plus `bull_bear_debate`.

## Example prompts

- "Analyze my watchlist and tell me which stocks to consider buying"
- "Do a technical analysis of TCS.NS"
- "Compare RELIANCE.NS, HDFCBANK.NS and INFY.NS"
- "What is moving in the market today?"
- "Screen for quality value stocks with P/E under 25 and RSI between 40 and 70"
- "How does AAPL correlate with the S&P 500?"

## Troubleshooting

| Symptom | Fix |
|---|---|
| Tools do not appear in the client | Start a new session; confirm the absolute path to `server.py`; check the client logs |
| `ModuleNotFoundError: No module named 'mcp'` or `yfinance` | `pip install -r requirements.txt` |
| SSL certificate errors | `pip install certifi` |
| Alpha Vantage returns an “Information” message | Free tier was hit or the symbol is not supported for that endpoint |
| MongoDB journal not persisting | Confirm `MONGODB_URI` and `MONGODB_DB_NAME` or allow the JSON fallback |
| Empty or inconsistent market-movers data | NSE/BSE endpoints are rate-limited and cached; retry after a short pause |

## Repository layout

```text
stock_market_mcp/
├── app.py                  # Shared FastMCP instance
├── backtest.py             # Backtest harness for the scoring model
├── config.py               # .env loading and runtime config
├── e2e_test.py             # MCP handshake validation
├── prompts/
│   └── debate.py           # bull_bear_debate prompt
├── requirements.txt        # Project dependencies
├── server.py               # Entrypoint: imports all modules and runs MCP stdio
├── tools/
│   ├── __init__.py
│   ├── analysis.py         # analyze_stock, analyze_watchlist, compare_stocks
│   ├── classification.py   # sector_mapping
│   ├── core.py             # quote, search, technicals, alpha vantage overview
│   ├── derivatives.py      # options_data
│   ├── flows.py            # fii_dii_flows
│   ├── fundamentals.py     # currency_impact, dividend_calendar
│   ├── journal.py          # log_decision, review_decisions, analyst_reports
│   ├── market.py           # market_movers, stock_news, earnings_calendar
│   └── screening.py        # stock_screener, correlation_analysis
├── utils/
│   ├── __init__.py
│   └── helpers.py          # _safe, RSI, MACD, Alpha Vantage helpers
├── wiki/                   # GitHub wiki pages
├── .gitignore
├── README.md
└── SESSION_NOTES.md
```

## Backtesting

`backtest.py` replays the scoring rules over recent market history and compares the signal against benchmark returns. The current findings are intentionally conservative: the technical score can have some short-horizon edge, but the rules are a screening aid rather than a proven predictive model.

## Acknowledgements

This project borrows the “grounded analyst reports → bull/bear debate → risk check → decision journal” workflow from TradingAgents and adapts it to an MCP server for NSE/BSE and US markets. The key difference is that the server handles the data retrieval and the client does the higher-level reasoning.

## Disclaimer

All output is educational analysis based on public market data and is not financial advice. BUY/HOLD/SELL recommendations are screening aids, not trade recommendations. Always do your own research and consult a qualified financial advisor before investing.

## License

MIT
