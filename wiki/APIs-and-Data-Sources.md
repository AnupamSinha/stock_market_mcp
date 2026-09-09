# APIs and Data Sources

| API | Role | Key? | Limits / gotchas |
|---|---|---|---|
| **Yahoo Finance** (`yfinance`) | primary: quotes, history, fundamentals, news | none | free; bursts can throttle — retry after a pause |
| **Alpha Vantage** | optional `alpha_vantage_overview` | `ALPHA_VANTAGE_API_KEY` in `.env` | free tier ~25 req/day, 1 req/sec; **NSE/BSE symbols return empty data** — US symbols only (verified live) |
| **bsedata** | BSE top gainers/losers for `market_movers` | none | scrapes bseindia.com — 10-min TTL cache, graceful fallback; BSE warns heavy scraping risks IP blocks |
| **MongoDB** | decision journal | none (local) | `MONGODB_URI` / `MONGODB_DB_NAME` env vars; auto JSON-file fallback |

## yfinance-specific notes (learned the hard way)

- **`dividendYield` is now in percent** (e.g. `0.46` = 0.46%). Do **not** multiply by 100 — earlier versions of this server did and showed impossible 46% yields.
- Some fields can be `NaN` — everything passes through `_safe()` which converts NaN/inf to `null`.
- `yf.download` of a single ticker may return a DataFrame, not a Series — always normalize.
- Symbols with no data return all-NaN columns — guard before indexing.

## Why Yahoo is primary for India

Alpha Vantage deprecated Indian fundamentals for free keys. Yahoo Finance covers
NSE (`.NS`) and BSE (`.BO`) for prices, fundamentals and news with no key — so it
carries everything except the optional `alpha_vantage_overview` tool.

## Roadmap source (not yet integrated)

A dedicated NSE news-sentiment source would upgrade `analyst_reports`' sentiment
block from headlines-only to scored sentiment. No free reliable provider identified yet.
