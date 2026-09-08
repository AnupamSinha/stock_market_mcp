# stock_market_mcp — Stock Analysis MCP Server

An MCP server that analyzes stocks and returns a scored **BUY / HOLD / SELL** assessment so you know which stocks to consider.

## APIs used

| API | Purpose | Key needed? |
|---|---|---|
| **Yahoo Finance** (via `yfinance`) | Quotes, price history, fundamentals, news — primary data source | No (free) |
| **Alpha Vantage** (optional) | Extra company overview data | Yes — free key at https://www.alphavantage.co/support/#api-key (5 req/min, 500/day) |

Set the key via env: `ALPHA_VANTAGE_API_KEY=...` — already configured in `.env` (loaded automatically by `server.py`).

> **Free-tier notes (verified live):** the free key is rate-limited to **~25 requests/day, 1 req/sec** — heavy use returns an "Information" notice instead of data. Alpha Vantage's `OVERVIEW` works for **US symbols** (AAPL ✔) but returns empty data for NSE/BSE symbols (RELIANCE.BSE ✘) — Indian-market coverage comes from Yahoo Finance, which is the primary source.

## Tools

| Tool | What it does |
|---|---|
| `get_quote` | Current price + day change for a symbol |
| `technical_analysis` | SMA 20/50/200, RSI-14, MACD, 52w range, volatility |
| `analyze_stock` | Full technical + fundamental scoring → BUY/HOLD/SELL with reasons |
| `analyze_watchlist` | Analyze & rank up to 15 symbols (default: Indian NSE large caps) |
| `compare_stocks` | Side-by-side P/E, margins, ROE, 1y return |
| `market_movers` | Index snapshot for India (NIFTY 50) or US (S&P 500) |
| `stock_news` | Recent headlines for a symbol |
| `alpha_vantage_overview` | Optional Alpha Vantage company overview |

Symbols: NSE → `RELIANCE.NS`, BSE → `500325.BO`, US → `AAPL`.

## Run

```bash
pip install -r requirements.txt
python server.py
```

## MCP client config

```json
{
  "mcpServers": {
    "stock_market_mcp": {
      "command": "python3",
      "args": ["/Users/anupamsinha/just-claude/stock_market_mcp/server.py"],
      "env": { "ALPHA_VANTAGE_API_KEY": "your_key_here" }
    }
  }
}
```

> **Disclaimer:** output is educational analysis, not financial advice.
