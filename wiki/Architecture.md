# Architecture

```
MCP client (ZCode / Claude / any MCP host)
   │  spawns on demand, speaks JSON-RPC over stdio
   ▼
server.py  (FastMCP, single process)
   │
   ├── Analysis tools ──────► Yahoo Finance (yfinance)     [no key, free]
   ├── alpha_vantage_overview ► Alpha Vantage REST          [optional key]
   ├── Decision journal ─────► MongoDB stock_data.decision_journal
   │                             └─ fallback: decision_journal.json
   └── bull_bear_debate ─────► executed by the CLIENT LLM,
                                 grounded on tool data only
```

## Design decisions

1. **Server = verified data, client = reasoning.** All numbers come from computed
   data (yfinance or our own indicator math). The LLM never supplies figures from
   memory — enforced by the `data_snapshot` audit block and the debate prompt's
   grounding rules. (Pattern borrowed from TradingAgents; see [[TradingAgents-Inspiration]].)

2. **Single file, stdio, no framework.** Deliberately not LangGraph/Docker — the
   client already *is* the LLM orchestration layer. Keeping the server thin keeps
   it fast to start, easy to audit, and free of LLM API costs per call.

3. **Graceful degradation everywhere.** No Alpha Vantage key → that one tool
   reports it's disabled. MongoDB down → journal falls back to a JSON file.
   Missing yfinance fields → `null`, never a fabricated number.

4. **India-first defaults.** Default watchlist, market movers, and examples all
   assume NSE/BSE; symbol formatting is documented per exchange.

## Scoring pipeline

`analyze_stock` computes the technical block (trend via SMAs, momentum via RSI/MACD,
6-month return) and the fundamental block (P/E, leverage, margin, dividend), applies
fixed point adjustments from a neutral 50, clamps to 0–100, and maps ≥60 → BUY,
≤20 → SELL, else HOLD. Every input value is returned in `data_snapshot` for audit.

## Module map (server.py)

| Section | Contents |
|---|---|
| config | `.env` loader, env vars |
| helpers | `_safe` (NaN→null), RSI, MACD, `_alpha_vantage` (certifi-aware) |
| analysis tools | quote, technical, analyze, watchlist, compare, movers, news |
| decision journal | Mongo insert/find + JSON fallback, `log_decision`, `review_decisions` |
| workflow | `analyst_reports`, `bull_bear_debate` prompt |
| main | `mcp.run()` (stdio) |
