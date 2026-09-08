# Decision Journal

Every recommendation the server (or its debate workflow) produces can be logged with
its rationale and the price at decision time — then measured later. This is the
forward-looking companion to [[Backtesting]]: backtest validates the *rules* on
history; the journal validates the *live calls* going forward.

## Write: `log_decision(symbol, action, rationale, score)`

- `action` must be BUY / HOLD / SELL
- Price at decision time is fetched automatically and stored
- Example: *"Log that I'm HOLDing RELIANCE at 45 with the trend-vs-valuation rationale"*

## Read: `review_decisions(symbol="")`

For each open decision: current price, return since decision, and a verdict:

| Action | CORRECT | WRONG | NEUTRAL |
|---|---|---|---|
| BUY | return > +1% | return < −1% | in between |
| SELL | return < −1% | return > +1% | in between |
| HOLD | — | — | \|return\| ≤ 5%; BROKEN beyond |

## Storage

- **Primary:** MongoDB collection `stock_data.decision_journal` (configurable via `MONGODB_URI`/`MONGODB_DB_NAME`)
- **Fallback:** if MongoDB is unreachable at call time, entries go to `decision_journal.json`
  next to `server.py` (gitignored). Note: the two stores are independent — nothing migrates
  automatically if you switch.

## Workflow integration

The `bull_bear_debate` prompt ends with a mandatory `log_decision` call, so every
debated decision is recorded with its full rationale — no untracked opinions.

## Honesty rules

- Verdicts use the fixed thresholds above — mechanical, not generous.
- HOLD decisions that drift >5% are marked BROKEN, not quietly excused.
- Nothing is ever deleted automatically; history is append-only.
