# Tools Reference

11 tools + 1 prompt. All analysis defaults to the Indian market (NSE `.NS` / BSE `.BO`); US tickers also work.

## Symbol formats

| Market | Format | Example |
|---|---|---|
| NSE (India) | `<SYMBOL>.NS` | `RELIANCE.NS`, `TCS.NS` |
| BSE (India) | `<CODE>.BO` | `500325.BO` |
| US | plain ticker | `AAPL` |

## Analysis tools

### `get_quote(symbol)`
Current price, previous close, day change %.

### `technical_analysis(symbol, period="6mo")`
SMA 20/50/200, RSI-14, MACD + signal + trend, 52-week high/low, daily volatility.

### `analyze_stock(symbol)` — the core tool
Technical + fundamental scoring → 0–100 score, **BUY (≥60) / HOLD / SELL (≤20)**, plain-English reasons, fundamentals block, and a **`data_snapshot`** (every input value, timestamped, with source — the audit trail).

### `analyze_watchlist(symbols="")`
Ranks up to 15 comma-separated symbols by score. Empty → default NSE large caps
(RELIANCE, TCS, INFY, HDFCBANK, ITC, SBIN).

### `compare_stocks(symbols)`
Side-by-side P/E, market cap, profit margin, ROE, debt/equity, dividend yield, 1-year return.

### `market_movers(market="india")`
Index snapshot — India (NIFTY 50) or US (S&P 500), with suggested next steps.

### `stock_news(symbol, limit=5)`
Recent headlines (title/publisher/link). Headlines only — tone judgment is left to the client LLM.

### `alpha_vantage_overview(symbol)`
Optional Alpha Vantage company overview. Needs `ALPHA_VANTAGE_API_KEY`. US symbols only (see [[APIs-and-Data-Sources]]).

## Decision journal

### `log_decision(symbol, action, rationale, score)`
Records a BUY/HOLD/SELL decision with the price at decision time. Stored in MongoDB
(`stock_data.decision_journal`) or `decision_journal.json` if MongoDB is unreachable.

### `review_decisions(symbol="")`
Prices every open decision, computes return since decision, and verdicts:
BUY → CORRECT (>+1%) / WRONG (<-1%) / NEUTRAL; SELL → inverse; HOLD → NEUTRAL while within ±5%,
BROKEN beyond. See [[Decision-Journal]].

## Workflow

### `analyst_reports(symbol)`
Three independent, timestamped reports: **fundamentals**, **technical**, **sentiment** (headlines).
The input for the debate prompt.

### Prompt: `bull_bear_debate(symbol)`
TradingAgents-inspired workflow the client LLM executes:
gather reports → bull case → bear case → risk check (falsification conditions, sizing, upcoming events)
→ decision with score + confidence + horizon → `log_decision` automatically.
Grounding rule: every claim must trace to the snapshot or a fresh tool call.

## Scoring model (current, beta)

Starts neutral at 50; adjustments: price vs 50-day SMA ±10, vs 200-day SMA ±10,
RSI <30 +10 / >70 −10, MACD crossover ±5, positive 6-month return +5,
P/E <25 +10 / ≥60 −5, debt-to-equity <100 +5 else −5, profit margin >10% +5, dividend yield +5.

⚠️ See [[Backtesting]]: these weights are conventions, not yet fully evidence-tuned.
