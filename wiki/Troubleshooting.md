# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tools don't appear in the client | Client spawns the server at session start | Start a **new conversation/session**; verify absolute path to `server.py`; check the client's MCP logs |
| `ModuleNotFoundError: mcp` / `yfinance` | Wrong Python or missing install | `pip install -r requirements.txt` with the **same** interpreter that runs `server.py` |
| `CERTIFICATE_VERIFY_FAILED` (macOS) | Python without CA certs | `pip install certifi` — the server uses it automatically |
| Alpha Vantage "Information" message | Free-tier rate limit (~25 req/day, 1/sec) | Wait, or use the Yahoo-based tools (they're the primary anyway) |
| `alpha_vantage_overview` says key not set | `.env` missing or wrong dir | Put `.env` next to `server.py`, or export `ALPHA_VANTAGE_API_KEY` |
| Alpha Vantage empty result for NSE symbol | Alpha Vantage dropped Indian fundamentals | Expected — use `analyze_stock` (Yahoo-based) |
| Impossible dividend yield (e.g. 460%) | Old server version double-scaled units | Update — yfinance's `dividendYield` is already percent; fixed in this codebase |
| Journal entries vanish | MongoDB was up, then down (or vice versa) | Check which store you're reading: MongoDB `stock_data.decision_journal` vs `decision_journal.json` — they don't sync |
| `yfinance` returns empty/errors for a burst of calls | Yahoo throttling | Pause and retry; reduce watchlist size |
| Backtest `KeyError: NaT` / empty quintiles | Fixed in current `backtest.py` | Pull latest; the script guards all-NaN symbols and duplicate bin edges |

## Diagnostics one-liner

```bash
python3 -c "import yfinance as yf; print(yf.Ticker('RELIANCE.NS').fast_info.last_price)"
```

If this prints a price, network + yfinance are fine and the issue is client config.
