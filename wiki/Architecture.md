# Architecture

```
   MCP client (ZCode / Claude / any host)
      │  launches over stdio
   ▼
   server.py
   │
      ├── app.py                     # shared FastMCP singleton
      ├── config.py                  # loads .env and runtime settings
      ├── tools/
      │   ├── core.py                # quotes, symbol search, technical data
      │   ├── analysis.py            # scorecards, ranking, compare
      │   ├── market.py              # movers, news, earnings
      │   ├── screening.py           # screener and correlation
      │   ├── fundamentals.py        # currency and dividend tools
      │   ├── derivatives.py         # options data
      │   ├── classification.py      # sector and peer metadata
      │   ├── flows.py               # institutional/insider activity
      │   └── journal.py             # decision journal and analyst reports
      ├── prompts/debate.py          # bull_bear_debate prompt
      ├── utils/helpers.py           # safe conversion, RSI, MACD, asset fetch helpers
      ├── backtest.py                # scoring-model replay/harness
      └── e2e_test.py                # MCP handshake validation
   ```

   ## Design principles

   1. **Server owns the data layer.** Quotes, history, fundamentals, and market context come from Yahoo Finance or exchange endpoints; the client does not have to guess values.

   2. **The client owns reasoning.** The MCP host can decide which tools to call and how to explain them. The server does not perform LLM reasoning or produce narrative investment advice itself.

   3. **Grounding is enforced by the workflow.** `analyze_stock` and `analyst_reports` both emit audit-oriented data snapshots, and `bull_bear_debate` explicitly tells the client to ground claims in tool output rather than memory.

   4. **Failure modes degrade gracefully.** Missing Alpha Vantage keys disable only that tool. A MongoDB outage falls back to a local JSON file. Empty fields are represented as `null`, not invented.

   5. **India-first but not India-only.** NSE/BSE logic and defaults are first-class, but the same tool layer works for US equities as well.

   ## Scoring pipeline

   `analyze_stock` computes a technical block and a fundamental block, then applies a neutral 50-point baseline and adjusts up or down based on the observed values. The final result is mapped to:

   - BUY: higher end of the score range
   - HOLD: middle range
   - SELL: lower end of the range

   The output includes reasons and a `data_snapshot` block so the result can be checked line by line.

   ## Module map

   | Module | Responsibility |
   |---|---|
   | `server.py` | Imports all modules and starts the MCP stdio server |
   | `app.py` | Establishes the shared `FastMCP` instance |
   | `config.py` | `.env` config, environment defaults |
   | `tools/core.py` | Quotes, search, technicals, optional Alpha Vantage overview |
   | `tools/analysis.py` | Scorecards and ranked watchlists |
   | `tools/market.py` | Market movers, earnings, and headlines |
   | `tools/screening.py` | Screening and correlation analysis |
   | `tools/fundamentals.py` | Dividend and currency analysis |
   | `tools/derivatives.py` | Options-chain metrics |
   | `tools/classification.py` | Sector/industry metadata |
   | `tools/flows.py` | Institutional holders and insider activity |
   | `tools/journal.py` | Decision logging and outcome review |
   | `prompts/debate.py` | Debate workflow + grounding rules |
   | `utils/helpers.py` | Shared helper functions, conversions, and indicators |

   ## Data flow

   1. The MCP client calls a tool.
   2. The tool queries Yahoo Finance, public exchange endpoints, or optional Alpha Vantage.
   3. Data is normalized via helper functions.
   4. The tool returns JSON to the client.
   5. The reasoning layer combines these outputs into a report, watchlist ranking, or debate answer.
   6. If needed, the decision journal records the output and can later grade it against current prices.
