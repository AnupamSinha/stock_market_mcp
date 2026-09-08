# 🧠 FoodForBrains — stock_market_mcp

> **FoodForBrains** · *Feeding your brain the data it needs to decide.*

Welcome to the official wiki for **stock_market_mcp** — FoodForBrains' lightweight, India-focused (NSE/BSE) stock-analysis MCP server that returns scored **BUY / HOLD / SELL** assessments from live market data.

## Quick start

```bash
git clone https://github.com/AnupamSinha/stock_market_mcp.git
cd stock_market_mcp && pip install -r requirements.txt
python3 server.py   # launched automatically by your MCP client
```

Full walkthrough: [[Setup-and-Installation]]

## Pages

| Page | Contents |
|---|---|
| [[Setup-and-Installation]] | Prerequisites, install, client configuration (ZCode / Claude Desktop) |
| [[Tools-Reference]] | All 11 tools + 1 prompt, parameters, scoring model |
| [[Architecture]] | How the server is built; data flow; design decisions |
| [[APIs-and-Data-Sources]] | Yahoo Finance, Alpha Vantage, MongoDB — limits and gotchas |
| [[Decision-Journal]] | Logging decisions, reviewing outcomes, JSON fallback |
| [[Backtesting]] | The harness, methodology, current findings |
| [[TradingAgents-Inspiration]] | What we borrowed from TauricResearch/TradingAgents and why |
| [[Troubleshooting]] | Common errors and fixes |
| [[FAQ]] | Frequently asked questions |

## What it gives you

- **11 tools + 1 prompt** — quotes, technicals (SMA/RSI/MACD), full scored analysis with auditable data snapshots, watchlist ranking, comparisons, news, and a TradingAgents-style bull/bear debate workflow
- **Decision journal** — every recommendation logged and later graded CORRECT/WRONG against real prices
- **Backtest harness** — the scoring rules replayed over 5 years of NSE history, honestly reported
- **Zero mandatory API keys** — Yahoo Finance powers everything; Alpha Vantage is optional

## About FoodForBrains

FoodForBrains builds tools that make market information digestible — analysis
you can actually reason about, with every number traceable to its source.
This project is part of that mission: grounded data in, transparent reasoning
out.

## Disclaimer

All content and tool output is **educational analysis generated from public market data — not financial advice**. BUY/HOLD/SELL scores are a screening aid, not a recommendation to trade. Invest responsibly — your brain deserves the whole meal. 🧠
