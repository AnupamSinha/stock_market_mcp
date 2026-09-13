# Tools Reference

This project exposes **20 MCP tools + 1 prompt**. Most workflows default to Indian market conventions (NSE `.NS` and BSE `.BO`), but US tickers also work.

## Symbol formats

| Market | Format | Example |
|---|---|---|
| NSE (India) | `<SYMBOL>.NS` | `RELIANCE.NS`, `TCS.NS` |
| BSE (India) | `<CODE>.BO` | `500325.BO` |
| US | plain ticker | `AAPL`, `MSFT` |

## Core market tools

### `get_quote(symbol)`
Returns current price, previous close, and change percentage.

### `search_symbol(query, limit=8)`
Resolves company names or partial queries to tradeable symbols. Results are sorted India-first (`.NS`, then `.BO`, then other exchanges).

### `technical_analysis(symbol, period="6mo")`
Returns SMA 20/50/200, RSI-14, MACD, MACD signal, 52-week high/low, and daily volatility.

### `market_movers(market="india")`
Returns NSE/BSE gainers and losers plus the market index. It uses public exchange data with caching and graceful degradation.

### `stock_news(symbol, limit=5)`
Returns recent news headlines with publisher and link information.

### `earnings_calendar(symbol)`
Returns next earnings date, days until, EPS estimate, and recent EPS history / surprise percentages.

### `alpha_vantage_overview(symbol)`
Optional Alpha Vantage company overview. Requires `ALPHA_VANTAGE_API_KEY` and is most useful for US tickers; Indian symbols usually return empty data.

## Analysis tools

### `analyze_stock(symbol)`
The core scorecard. Combines technical and fundamental inputs, returns a `score` from 0–100, a recommendation, reasons, and a `data_snapshot` containing the underlying values used to compute the score.

### `analyze_watchlist(symbols="")`
Ranks a comma-separated list of symbols by score. Defaults to a large-cap India watchlist when no symbols are supplied.

### `compare_stocks(symbols)`
Compares several symbols side by side on P/E, market cap, profit margin, ROE, debt/equity, dividend yield, and 1-year return.

### `stock_screener(symbols="", min_pe=None, max_pe=None, min_rsi=None, max_rsi=None, min_dividend_yield=None, min_roe=None, min_score=None)`
Filters a list of candidate symbols against valuation and momentum thresholds.

### `correlation_analysis(symbol, benchmark="^NSEI", period="1y")`
Computes correlation, beta, r-squared, and 30-day rolling correlation relative to a benchmark index.

## Fundamentals and context tools

### `currency_impact(symbol)`
Shows INR vs USD returns for Indian equities and the net currency contribution.

### `dividend_calendar(symbol)`
Returns dividend yield, annual rate, payout ratio, ex-dividend date, and recent payout history.

### `options_data(symbol)`
Fetches the options chain and returns IV, put/call ratios, ATM contracts, and sentiment signals when available.

### `sector_mapping(symbol)`
Returns sector, industry, peer tickers, company summary, beta, and key financial metrics.

### `fii_dii_flows(symbol="", period="1m")`
Shows institutional holders, mutual-fund holders, and insider activity for a symbol where Yahoo Finance provides it. Market-wide FII/DII flows require a paid NSE API and are not available here.

## Decision journal and workflow

### `log_decision(symbol, action, rationale="", score=None)`
Records a BUY/HOLD/SELL decision in MongoDB (`stock_data.decision_journal`) or a local JSON fallback file when MongoDB is unavailable.

### `review_decisions(symbol="")`
Evaluates open decisions against current prices and classifies them as CORRECT, WRONG, NEUTRAL, or BROKEN depending on the action and return since the decision date.

### `analyst_reports(symbol)`
Generates three separate reports: fundamentals, technicals, and sentiment/news headlines.

### Prompt: `bull_bear_debate(symbol)`
A TradingAgents-style workflow that asks the client model to:

1. Gather the `analyst_reports` output for the symbol
2. Build the bull case from the snapshot data only
3. Build the bear case from the snapshot data only
4. Check the risk and falsification conditions
5. Make a decision with a score, confidence, and time horizon
6. Call `log_decision` with the final rationale

## How the score is computed

The current score starts from 50 and adds or subtracts points based on:

- price vs 50-day and 200-day SMA
- RSI-14 oversold/overbought conditions
- MACD relative to signal line
- 6-month return
- P/E versus valuation thresholds
- debt/equity and leverage
- profit margin
- dividend yield

The exact weights are still a practical heuristic rather than a fully proven model. See [[Backtesting]] for the current evidence and caveats.

## Grounding and audit rules

The server is designed around “verified data first.” For example, `analyze_stock` and `analyst_reports` attach a `data_snapshot` that includes the values used to compute the recommendation and the source of each figure.

This keeps the model honest: the reasoning layer must cite fresh tool output, not memory.
