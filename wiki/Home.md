# 🧠 FoodForBrains — stock_market_mcp

> **FoodForBrains** · *Feeding your brain the data it needs to decide.*

Welcome to the official wiki for **stock_market_mcp**. This project is a lightweight MCP server for stock research, ranking, and screening across the Indian market and major US tickers.

It exposes a verified-data layer for AI clients: every quote, indicator, and recommendation is grounded in source data rather than memory. The server is intentionally simple and thin; the client remains responsible for higher-level reasoning.

## Quick start

```bash
git clone https://github.com/AnupamSinha/stock_market_mcp.git
cd stock_market_mcp
pip install -r requirements.txt
python3 server.py   # typically launched by your MCP client
```

Full setup: [[Setup-and-Installation]]

## What is included

- **20 tools + 1 prompt** for quotes, technicals, screening, comparison, sector context, journal logging, and structured debate
- **India-first defaults** for NSE/BSE symbols, but US tickers also work
- **Grounded snapshots** so numbers can be traced to the source data
- **Zero mandatory API keys** for core analysis; Alpha Vantage is optional
- **Journal grading loop** to compare decisions against current prices

## Wiki pages

| Page | Contents |
|---|---|
| [[Setup-and-Installation]] | Prerequisites, install, env vars, MCP client configuration |
| [[Tools-Reference]] | Tool catalog for all 20 MCP tools and the `bull_bear_debate` prompt |
| [[Architecture]] | Server design, module map, data flow, and grounding model |
| [[APIs-and-Data-Sources]] | Yahoo Finance, NSE/BSE sources, Alpha Vantage, MongoDB, and limits |
| [[Decision-Journal]] | Logging calls, reviewing them against prices, fallback behavior |
| [[Backtesting]] | The scoring-model harness and current findings |
| [[TradingAgents-Inspiration]] | Why the workflow borrows from TradingAgents and how this server adapts it |
| [[Troubleshooting]] | Common setup and runtime issues |
| [[FAQ]] | Frequently asked questions |

## About FoodForBrains

FoodForBrains builds tools that make market information digestible. This project follows that principle: grounded data in, transparent reasoning out.

## Disclaimer

All content and tool output is educational analysis generated from public market data, not financial advice. BUY/HOLD/SELL scores are screening aids, not trade recommendations.
