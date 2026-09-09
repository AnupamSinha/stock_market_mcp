---
name: stock-market-mcp
description: Analyze Indian (NSE/BSE) and US stocks via the stock_market_mcp MCP server — quotes, technicals (SMA/RSI/MACD), scored BUY/HOLD/SELL analysis with auditable data snapshots, watchlist ranking, BSE+NSE market movers, stock news, symbol search, a bull/bear debate workflow, and a decision journal that grades past calls. Use when the user asks about stock prices, whether to buy/sell/hold a stock, market movers, comparing stocks, or wants a stock researched or debated.
---

# stock-market-mcp — how to drive the server

`stock_market_mcp` is an MCP server (17 tools + 1 prompt). It is a **verified-data layer**:
every number comes from Yahoo Finance, nseindia.com, or bsedata — never from your memory.
Your job as the client LLM is reasoning, judgment, and honest reporting of the data.

**Golden rule: every claim you make about a stock must trace to a tool result in this
conversation. If you have no fresh data, call a tool or say so — never fill gaps from memory.**

## Symbols

| Market | Format | Example |
|---|---|---|
| NSE | `<SYMBOL>.NS` | `RELIANCE.NS` |
| BSE | `<CODE>.BO` | `500325.BO` |
| US | plain ticker | `AAPL` |

Only have a company name? Call `search_symbol` first (India-first ranking; falls back to
direct-symbol validation). Note: some famous tickers are gone — e.g. `TATAMOTORS.NS` was
delisted after the demerger; trust what `search_symbol` returns, not your memory.

## Tool selection guide

| User intent | Tool(s) |
|---|---|
| "What's the price of X?" | `get_quote` |
| "Find the symbol for X" | `search_symbol` |
| "Technical view on X" | `technical_analysis` |
| "Should I buy/sell X?" / "Analyze X" | `analyze_stock`, or the full `bull_bear_debate` prompt |
| "Which of these stocks looks best?" | `analyze_watchlist` (ranks by score) or `compare_stocks` (fundamentals side-by-side) |
| "Screen stocks by P/E, RSI, dividend yield" | `stock_screener` |
| "What's moving in the market?" | `market_movers` (NSE + BSE gainers/losers + NIFTY) |
| "Any news on X?" | `stock_news` |
| "When does X report earnings?" / "EPS estimate for X" | `earnings_calendar` |
| "How does X correlate with NIFTY/S&P?" | `correlation_analysis` |
| "Currency impact on my NRI returns?" | `currency_impact` |
| "Dividend dates and yield for X?" | `dividend_calendar` |
| "Deep-dive debate on X" | `bull_bear_debate` prompt (uses `analyst_reports`) |
| "Record my call" / "How did our calls do?" | `log_decision` / `review_decisions` |

## Understanding `analyze_stock` output

- `score` (0–100) → `recommendation`: **BUY ≥60, SELL ≤20, else HOLD**. The SELL bucket
  is rare — most bearish states land in HOLD territory.
- `reasons[]` — the exact rules that fired; quote these, don't invent new ones.
- `data_snapshot` — the audit trail (as-of date, every indicator value, source). When you
  explain a recommendation, cite the snapshot values.
- `fundamentals` fields can be `null` when Yahoo lacks them — say "not available", never guess.

**Scoring caveats you must convey when relevant:** the backtest (5y NIFTY-100) found the
technical rules have modest 1–3-month momentum signal and little long-horizon power;
weights are conventions, not proof. The score is a *screening aid*, not advice.

## The debate workflow (`bull_bear_debate` prompt)

For any "should I buy X" question worth depth, use the prompt — it enforces:
gather (`analyst_reports`) → bull case → bear case → risk check → decision with score +
confidence + horizon → `log_decision`. Steelman both sides; ground every claim in the
reports; state what would falsify each case.

## Decision journal discipline

- After any decision you present as actionable, `log_decision` it (action, score, one-paragraph rationale).
- When the user asks "how are we doing", call `review_decisions` — it grades every open
  call CORRECT / WRONG / NEUTRAL against current prices. Report failures honestly; never
  delete journal history.

## Using `earnings_calendar`

- **Upcoming earnings:** Returns the next earnings date, days until, and analyst EPS estimate.
- **Recent history:** Shows last 4 quarters with EPS estimates, reported EPS, and surprise %.
- **Use cases:** Risk assessment in debates ("earnings in 14 days — last beat was +12%, watch for volatility"), valuation timing, catalyst awareness.
- **Indian stocks:** Often don't publish scheduled dates in advance — returns recent history with surprise % instead.
- **US stocks:** Typically have scheduled dates (e.g., AAPL Oct 29, MSFT ~last week of month).

## Using `stock_screener`

- **Filters:** `min_pe`, `max_pe`, `min_rsi`, `max_rsi`, `min_dividend_yield`, `min_roe`, `min_score`
- **Input:** Comma-separated symbols (default: default watchlist RELIANCE, TCS, INFY, HDFCBANK, ITC, SBIN)
- **Output:** Matching stocks with P/E, RSI, dividend yield, ROE, and analyze_stock score
- **Example:** `stock_screener("", min_pe=10, max_pe=25, min_rsi=40, max_rsi=70)` → stocks with P/E 10-25 and RSI 40-70
- **Use cases:** Finding oversold value stocks, high-dividend payers, momentum stocks

## Using `correlation_analysis`

- **Benchmarks:** `^NSEI` (NIFTY 50), `^GSPC` (S&P 500), `^BSESN` (BSE Sensex)
- **Outputs:** `correlation` (Pearson coefficient), `beta`, `r_squared`, rolling 30-day correlation
- **Interpretation:** correlation > 0.7 = high, 0.4-0.7 = moderate, < 0.4 = low
- **Beta:** > 1 = more volatile than benchmark, < 1 = less volatile
- **Use cases:** Portfolio construction ("add low-correlation stocks for diversification"), risk assessment

## Using `currency_impact`

- **Purpose:** Shows returns in both INR and USD for Indian stocks
- **Useful for:** NRIs, foreign investors tracking Indian equities
- **Outputs:** INR return, USD return, currency impact percentage
- **Interpretation:** Positive currency impact = rupee weakened (helped USD returns), negative = rupee strengthened
- **Example:** Stock up 15% in INR but only 8% in USD → rupee strengthened, 7% currency drag

## Using `dividend_calendar`

- **Outputs:** Dividend yield, annual rate, ex-dividend date, recent payment history
- **Indian stocks:** Quarterly or annual dividends (many only announce annually)
- **US stocks:** Typically quarterly dividends with announced ex-dates
- **Use cases:** Income investing, ex-dividend capture timing, yield comparison

## Gotchas

- **Beta-API fragility:** `market_movers` hits nseindia.com and bseindia.com (cached 10 min).
  If a movers block is `null` with an error, say "exchange movers unavailable right now"
  and fall back to `analyze_watchlist` on known symbols. Fun fact: NSE's losers endpoint
  is spelled `loosers` (their typo) — handled internally, but don't "fix" it.
- **Alpha Vantage** (`alpha_vantage_overview`) works for **US symbols only**, ~25 requests/day.
  For Indian stocks always use the Yahoo-based tools.
- **yfinance throttling:** a burst of calls can return empty — slow down or retry once,
  don't hammer.
- **HOLD is a valid answer.** Bearish trend + fair valuation genuinely scores HOLD.
  Prefer "no edge" over false confidence.

## Mandatory disclaimer

Conclude any substantive analysis with: educational analysis from public data, **not
financial advice**. Keep it one line; don't lecture.
