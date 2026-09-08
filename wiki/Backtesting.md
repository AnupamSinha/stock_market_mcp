# Backtesting

`backtest.py` answers one question with data: **do BUY-scored stocks actually
outperform SELL/HOLD-scored ones?** It replays the scoring rules on history
instead of trusting conventions.

## Method

- **Universe:** ~100 NSE stocks (NIFTY 50 + Next 50 proxy)
- **Window:** 5 years of daily adjusted closes (~1,240 trading days)
- **Rebalance:** each month-end, score every stock with the exact technical
  rules from `analyze_stock`, using **only data up to that date** (no lookahead)
- **Measure:** forward 1/3/6/12-month returns per score bucket and per score
  quintile, benchmarked against NIFTY 50 mean forward returns over the same windows
- **Buckets:** BUY ≥60, SELL ≤20, else HOLD (same cutoffs as the server)

## Current findings (beta weights)

1. **BUY ≈ HOLD** — the score's level doesn't separate winners at 6–12 months.
   Outperformance vs NIFTY is explained by survivorship bias, not skill.
2. **Weak short-horizon momentum** — top-quintile scores beat bottom-quintile at
   1–3 months (e.g. +6.7% vs +4.4% 3m) — the only edge currently evidenced.
3. **SELL never triggers** — the technical-only score floor (~15) makes the ≤20
   cutoff nearly unreachable; server SELL calls come from the fundamental half.
4. **Non-monotonic long end** — Q4, not Q5, had the best 6-month returns:
   long-horizon ranking power is absent.

## Known limitations (stated in the output too)

- Technical rules only — yfinance has no point-in-time historical fundamentals
- Survivorship bias — universe is today's index members
- No transaction costs, slippage, or taxes

## Outputs

- Console tables (buckets + quintiles + BUY−SELL spread)
- `backtest_results.csv` — every stock-month with score, bucket, forward returns
- `backtest_summary.json` — machine-readable summary

## Next measurable steps

1. Per-rule ablation (score each rule in isolation; keep what separates quintiles)
2. Point-in-time fundamentals source to backtest the value half
3. Re-tune weights toward the evidenced short-horizon momentum signal
