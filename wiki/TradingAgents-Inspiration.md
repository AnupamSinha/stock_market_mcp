# TradingAgents Inspiration

This server's workflow borrows ideas from
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
(Apache-2.0) — a multi-agent LLM framework simulating a trading firm. Thank you
to its maintainers for open-sourcing the architecture.

## What we took

| TradingAgents idea | Our implementation |
|---|---|
| Analyst team producing separate reports | `analyst_reports` — fundamentals / technical / sentiment, each timestamped |
| Grounded claims from a verified data snapshot | `data_snapshot` audit block in `analyze_stock`; debate prompt rule: "every claim traces to the snapshot or a fresh tool call" |
| Bull vs bear researcher debate | `bull_bear_debate` prompt — client LLM steelmans both sides from grounded data |
| Risk management check | debate step 4: falsification conditions, position sizing, upcoming events |
| Decision log with reflection | decision journal: `log_decision` / `review_decisions` with mechanical outcome verdicts |

## What we deliberately did NOT take (and why)

- **The LangGraph orchestration stack** — the MCP client is already the LLM layer;
  a thin server avoids per-analysis LLM cost and startup weight.
- **US-centric data sources** — StockTwits/Reddit have thin NSE coverage, FRED is
  US macro, Polymarket irrelevant. India needs different sentiment sources.
- **The simulated exchange** — research-only artifact; our journal + backtest
  harness serve the evaluation role.

## Attribution

Acknowledged in the repository README and in
[TauricResearch/TradingAgents issue #1313](https://github.com/TauricResearch/TradingAgents/issues/1313).
