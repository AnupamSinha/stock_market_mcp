# SESSION_NOTES.md — compressed handoff for future sessions

> Purpose: a successor session (or you, weeks later) can resume from this file
> alone. Read top to bottom; each section is self-contained.

## What this project is

`stock_market_mcp` — an MCP server (FastMCP, stdio) that analyzes stocks and
returns scored BUY/HOLD/SELL recommendations. **India focus: NSE (`.NS`) and
BSE (`.BO`) symbols only for analysis defaults; US tickers also work.**

- Entry point: `server.py` (run via MCP client config, not by hand)
- Repo: https://github.com/AnupamSinha/stock_market_mcp (private)
- Local path: `/Users/anupamsinha/just-claude/stock_market_mcp`

## Data sources / APIs

| API | Role | Notes |
|---|---|---|
| Yahoo Finance (`yfinance`) | primary: quotes, history, fundamentals, news | free, no key |
| Alpha Vantage | optional `alpha_vantage_overview` | key in `.env` (NOT committed); free tier ~25 req/day; **returns empty data for NSE/BSE symbols** — works US only |
| MongoDB `stock_data` | decision journal | falls back to `decision_journal.json` if down |

Gotcha (fixed, don't reintroduce): yfinance's `dividendYield` is now already
in **percent** — do not multiply by 100.

## Tools & prompts (11 tools + 1 prompt)

Analysis: `get_quote`, `technical_analysis`, `analyze_stock` (score + reasons
+ `data_snapshot`), `analyze_watchlist` (ranks, default NSE list),
`compare_stocks`, `market_movers`, `stock_news`, `alpha_vantage_overview`.
Journal: `log_decision`, `review_decisions` (CORRECT/WRONG/NEUTRAL verdicts).
Workflow: `analyst_reports` (fundamentals/technical/sentiment reports) +
`bull_bear_debate` prompt (TradingAgents-style: reports → bull → bear → risk
check → decision → auto-log).

## ZCode client config (done)

`~/.zcode/cli/config.json` → `mcp.servers.stock_market_mcp` →
`python3 /Users/anupamsinha/just-claude/stock_market_mcp/server.py`.
Connects automatically each session. A LaunchAgent auto-start experiment was
removed at user request — clients spawn the server on demand.

## Backtest findings (backtest.py, 5y NIFTY-100, technical rules only)

- Modest short-horizon (1–3m) ranking power (Q1 vs Q5 quintile spread).
- BUY and HOLD score levels indistinguishable at 6–12m.
- SELL cutoff (≤20) never triggers on the technical-only score — server SELL
  calls today come from the fundamental half.
- Limitations: survivorship bias (today's index members), no historical
  point-in-time fundamentals via yfinance, no costs.
- Next measurable steps: per-rule ablation; point-in-time fundamentals source;
  tune RSI/MACD weights (current evidence favors short-horizon momentum).

## Journal state

Two open HOLD decisions logged (MongoDB `stock_data.decision_journal`,
2026-09-08): RELIANCE.NS HOLD@1294.90 (score 45), INFY.NS HOLD@1082.00
(score 40). Check `review_decisions` for outcomes as prices move.

## User preferences (important)

- User wants requests **validated and confirmed before acting** on anything
  destructive or questionable — don't blindly execute.
- Educational-analysis framing everywhere; never financial advice.
- Alpha Vantage key exists (in `.env`); never commit it; never print it.

## Outstanding ideas (not built)

- India news-sentiment scoring (TradingAgents' sentiment agents don't port —
  StockTwits/Reddit too US-thin; would need a dedicated NSE news source).
- Earnings-calendar / event awareness in the risk check.
- Sector-relative indicator context (z-scores vs sector peers).
