"""
Backtest harness for the stock_market_mcp scoring rules.

Replicates the TECHNICAL half of server.analyze_stock() as it stood at each
month-end over ~5 years, then measures forward returns by score bucket
(BUY / HOLD / SELL, same cutoffs as the server: >=60 / 20-60 / <=20).

Limitations (printed with the results):
- Technical rules only — historical point-in-time fundamentals are not
  available via yfinance, so the fundamental half of the score is excluded.
- Universe = today's index members -> survivorship bias.
- No transaction costs, no slippage.

Run:  python3 backtest.py
"""
import json
import sys
import time

import numpy as np
import pandas as pd
import yfinance as yf

YEARS = 5
FORWARD_HORIZONS = {"1m": 21, "3m": 63, "6m": 126, "12m": 252}  # trading days

# NIFTY 100 proxy: NIFTY 50 + NIFTY Next 50 members (as of 2025)
UNIVERSE = [
    "ADANIENT","ADANIPORTS","APOLLOHOSP","ASIANPAINT","AXISBANK","BAJAJ-AUTO",
    "BAJFINANCE","BAJAJFINSV","BEL","BHARTIARTL","CIPLA","COALINDIA",
    "DRREDDY","EICHERMOT","ETERNAL","GRASIM","HCLTECH","HDFCBANK","HDFCLIFE",
    "HEROMOTOCO","HINDALCO","HINDUNILVR","ICICIBANK","INDUSINDBK","INFY","ITC",
    "JIOFIN","JSWSTEEL","KOTAKBANK","LT","M&M","MARUTI","NESTLEIND","NTPC",
    "ONGC","POWERGRID","RELIANCE","SBILIFE","SBIN","SHRIRAMFIN","SUNPHARMA",
    "TATACONSUM","TATAMOTORS","TATASTEEL","TCS","TECHM","TITAN","TRENT","ULTRACEMCO",
    "WIPRO","ABB","ADANIPOWER","AMBUJACEM","BANKBARODA","BPCL","BOSCHLTD",
    "BRITANNIA","CANBK","CHOLAFIN","DABUR","DIVISLAB","DLF","DMART","GAIL",
    "GODREJCP","HAVELLS","HAL","ICICIGI","INDIGO","IOC","INDHOTEL","IRFC",
    "JINDALSTEL","JSWENERGY","LICI","LTIM","MOTHERSON","NAUKRI","PIDILITIND",
    "PFC","PNB","RECLTD","SHREECEM","SIEMENS","SAIL","SUNTV","TATAPOWER",
    "TORNTPHARM","TVSMOTOR","UNITDSPR","VEDL","VBL","ZYDUSLIFE","ZOMATO",
    "LUPIN","AUROPHARMA","MUTHOOTFIN","OIL","PETRONET","IDEA","CUMMINSIND",
]


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    return ema12 - ema26, (ema12 - ema26).ewm(span=9, adjust=False).mean()


def technical_score(close: pd.Series, i: int) -> float:
    """The server's technical rules, evaluated using only data up to index i.

    Mirrors analyze_stock(): neutral start 50, same +/- adjustments,
    same BUY/HOLD/SELL cutoffs. SMA200 needs >=200 rows; without it the
    long-term rule is skipped (same as the server).
    """
    last = close.iloc[i]
    score = 50.0
    if i >= 50:
        score += 10 if last > close.iloc[i - 50] else -10
    if i >= 200:
        score += 10 if last > close.iloc[i - 200] else -10
    rsi = _rsi(close).iloc[i]
    if not np.isnan(rsi):
        if rsi < 30:
            score += 10
        elif rsi > 70:
            score -= 10
    if i >= 30:
        macd, signal = _macd(close.iloc[: i + 1])
        score += 5 if macd.iloc[-1] > signal.iloc[-1] else -5
    if i >= 126:
        ret_6m = (last / close.iloc[i - 126] - 1) * 100
        score += 5 if ret_6m > 0 else 0
    return float(min(100.0, max(0.0, score)))


def bucket(score: float) -> str:
    if score >= 60:
        return "BUY"
    if score <= 20:
        return "SELL"
    return "HOLD"


def main():
    print(f"Downloading {YEARS}y daily history for {len(UNIVERSE)} NSE symbols...")
    tickers = [s + ".NS" for s in UNIVERSE]
    px = yf.download(tickers, period=f"{YEARS}y", auto_adjust=True,
                     progress=False, threads=True)["Close"]
    if isinstance(px, pd.Series):
        px = px.to_frame()
    px = px.dropna(how="all")
    px = px.dropna(axis=1, how="all")  # drop symbols with no data at all
    print(f"Got {px.shape[1]}/{len(tickers)} symbols, {px.shape[0]} trading days.")

    # month-end decision dates with enough history for the rules
    month_ends = px.groupby(px.index.to_period("M")).tail(1).index
    month_ends = [d for d in month_ends if px.index.get_loc(d) >= 210]
    print(f"Scoring {len(month_ends)} month-ends x {px.shape[1]} stocks...")

    records = []
    for d in month_ends:
        i = px.index.get_loc(d)
        for t in px.columns:
            series = px[t].iloc[: i + 1]  # only data up to the decision date
            if len(series) < 210:
                continue
            si = len(series) - 1
            if np.isnan(series.iloc[si]) or px.index[si] < d - pd.Timedelta(days=10):
                continue  # no trade near this month-end
            score = technical_score(series, si)
            row = {"date": d, "symbol": t, "score": score, "bucket": bucket(score)}
            full = px[t]
            for name, n in FORWARD_HORIZONS.items():
                j = i + n
                if j < len(full) and not np.isnan(full.iloc[j]):
                    row[f"fwd_{name}"] = (full.iloc[j] / full.iloc[i] - 1) * 100
                else:
                    row[f"fwd_{name}"] = np.nan
            records.append(row)
    df = pd.DataFrame(records)
    print(f"Scored {len(df)} stock-months.\n")

    # index benchmark for excess-return context
    nifty = yf.download("^NSEI", period=f"{YEARS}y", auto_adjust=True,
                        progress=False)["Close"]
    if isinstance(nifty, pd.DataFrame):
        nifty = nifty.iloc[:, 0]
    nifty = nifty.dropna()
    bench = {}
    for name, n in FORWARD_HORIZONS.items():
        fwd = (nifty.shift(-n) / nifty - 1) * 100
        bench[name] = float(fwd.reindex(month_ends).mean())

    results = {}
    print("=" * 100)
    print(f"{'Bucket':6} | {'N':>6} | " +
          " | ".join(f"{'mean ' + h:>14}" for h in FORWARD_HORIZONS) +
          " | {'hit>0 (3m)':>10}")
    print("-" * 100)
    for b in ["BUY", "HOLD", "SELL"]:
        sub = df[df["bucket"] == b]
        if sub.empty:
            continue
        means = {h: sub[f"fwd_{h}"].mean() for h in FORWARD_HORIZONS}
        hit = (sub["fwd_3m"] > 0).mean() * 100 if sub["fwd_3m"].notna().any() else float("nan")
        results[b] = {"n": len(sub), "means": means, "hit_3m": hit}
        print(f"{b:6} | {len(sub):>6} | " +
              " | ".join(f"{means[h]:>10.2f}% ({bench[h]:+.2f}%)" for h in FORWARD_HORIZONS) +
              f" | {hit:>9.1f}%")
    print("=" * 100)

    if "BUY" in results and "SELL" in results:
        print("\nBUY minus SELL spread (annualized-ish view per horizon):")
        for h in FORWARD_HORIZONS:
            spread = results["BUY"]["means"][h] - results["SELL"]["means"][h]
            print(f"  {h:>4}: {spread:+.2f}%")
    # Quintile analysis — the fairer test of ranking power, since the
    # BUY/HOLD/SELL cutoffs assume the full (fundamental+technical) score.
    print("\nScore quintiles (Q1 = highest scores):")
    print(f"{'Quintile':9} | {'N':>6} | " +
          " | ".join(f"{'mean ' + h:>10}" for h in FORWARD_HORIZONS))
    print("-" * 80)
    df["quintile"] = pd.qcut(df["score"].rank(method="first"), 5,
                             labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
    for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
        sub = df[df["quintile"] == q]
        if sub.empty:
            continue
        means = {h: sub[f"fwd_{h}"].mean() for h in FORWARD_HORIZONS}
        print(f"{q:9} | {len(sub):>6} | " +
              " | ".join(f"{means[h]:>10.2f}%" for h in FORWARD_HORIZONS))

    print("\nLegend: 'mean 3m' = average forward 3-month return; "
          "(+x.xx%) = NIFTY 50 benchmark mean over the same windows.")
    print("Limitations: technical rules only (no historical fundamentals via yfinance); "
          "survivorship bias (today's index members); no costs/slippage.")

    df.to_csv("backtest_results.csv", index=False)
    with open("backtest_summary.json", "w") as f:
        json.dump({"by_bucket": results, "benchmark": bench}, f, indent=2, default=str)
    print("\nSaved: backtest_results.csv (full stock-month data), backtest_summary.json")


if __name__ == "__main__":
    sys.exit(main())
