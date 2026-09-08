# FAQ

**Is this financial advice?**
No. All output is educational analysis from public data via simple rules. The
BUY/HOLD/SELL scores are a screening aid — do your own research.

**Does it work only for Indian stocks?**
Defaults and examples are NSE/BSE-focused, and that's the design intent, but US
tickers (`AAPL`) work fine too since Yahoo Finance covers both.

**Do I need any API key?**
No. Yahoo Finance needs nothing. Alpha Vantage is optional (US-symbol overview only).

**Do I need MongoDB?**
Only for the decision journal. Without it, the journal falls back to a local JSON file.

**Where does the BUY/HOLD/SELL score come from?**
Fixed point adjustments around a neutral 50: trend (price vs 50/200-day SMA),
momentum (RSI-14, MACD), 6-month return, and fundamentals (P/E, leverage, margin,
dividend). Every input is returned in the `data_snapshot` block. See
[[Tools-Reference]] — and note the [[Backtesting]] findings before trusting the weights.

**How is this different from TradingAgents?**
Same workflow shape (reports → bull/bear debate → risk check → journaled decision),
but as a lightweight MCP server where the client LLM does the reasoning and the
server guarantees grounded data. See [[TradingAgents-Inspiration]].

**How do I know if the recommendations are any good?**
Two mechanisms: the backtest harness (rules vs history) and the decision journal
(live calls vs outcomes). Current evidence: modest short-horizon momentum edge,
little else — treat scores accordingly.

**Why HOLD so often?**
Both stocks in a bearish-trend-but-fair-valuation state honestly score HOLD.
The system prefers "no edge" over false confidence.

**Can multiple people use one server instance?**
Each client session spawns its own server process; the MongoDB journal is shared
across all of them.
