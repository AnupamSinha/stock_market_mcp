"""Derivatives tools: options_data."""
import json

import yfinance as yf

from utils.helpers import _safe

from app import mcp


@mcp.tool()
def options_data(symbol: str) -> str:
    """Options chain data: IV, put/call ratios, strike prices."""
    try:
        t = yf.Ticker(symbol)

        if not t.options:
            return json.dumps({"symbol": symbol, "error": "No options data available"})

        opt = t.option_chain(t.options[0])
        calls = opt.calls
        puts = opt.puts

        out = {"symbol": symbol, "source": "Yahoo Finance (yfinance)"}

        try:
            out["current_price"] = _safe(round(float(t.fast_info.last_price), 2))
        except Exception:
            pass

        out["expiration_dates"] = [str(d)[:10] for d in t.options] if t.options else []

        if not calls.empty:
            atm_mask = (calls["strike"] >= out.get("current_price", 0) * 0.95) & (
                calls["strike"] <= out.get("current_price", float("inf")) * 1.05
            )
            atm_calls = calls[atm_mask]
            if not atm_calls.empty:
                out["implied_volatility_call"] = _safe(
                    round(atm_calls["impliedVolatility"].mean() * 100, 2)
                )
            else:
                out["implied_volatility_call"] = _safe(round(calls["impliedVolatility"].mean() * 100, 2))

        if not puts.empty:
            atm_mask = (puts["strike"] >= out.get("current_price", 0) * 0.95) & (
                puts["strike"] <= out.get("current_price", float("inf")) * 1.05
            )
            atm_puts = puts[atm_mask]
            if not atm_puts.empty:
                out["implied_volatility_put"] = _safe(
                    round(atm_puts["impliedVolatility"].mean() * 100, 2)
                )
            else:
                out["implied_volatility_put"] = _safe(round(puts["impliedVolatility"].mean() * 100, 2))

        if not calls.empty and not puts.empty:
            call_vol = calls["volume"].sum()
            put_vol = puts["volume"].sum()
            call_oi = calls["openInterest"].sum()
            put_oi = puts["openInterest"].sum()

            out["put_call_volume_ratio"] = _safe(round(put_vol / call_vol, 3)) if call_vol > 0 else None
            out["put_call_oi_ratio"] = _safe(round(put_oi / call_oi, 3)) if call_oi > 0 else None

            if out.get("put_call_oi_ratio"):
                if out["put_call_oi_ratio"] > 1:
                    out["sentiment"] = "bearish (high put demand)"
                elif out["put_call_oi_ratio"] < 0.7:
                    out["sentiment"] = "bullish (high call demand)"
                else:
                    out["sentiment"] = "neutral"

        if not calls.empty and not puts.empty:
            price = out.get("current_price", 0)
            if price:
                call_strikes = calls[
                    (calls["strike"] >= price * 0.95) & (calls["strike"] <= price * 1.05)
                ]
                put_strikes = puts[
                    (puts["strike"] >= price * 0.95) & (puts["strike"] <= price * 1.05)
                ]

                out["atm_calls"] = [
                    {
                        "strike": _safe(row["strike"]),
                        "bid": _safe(row["bid"]),
                        "ask": _safe(row["ask"]),
                        "iv": _safe(round(row["impliedVolatility"] * 100, 2)),
                    }
                    for _, row in call_strikes.head(3).iterrows()
                ]
                out["atm_puts"] = [
                    {
                        "strike": _safe(row["strike"]),
                        "bid": _safe(row["bid"]),
                        "ask": _safe(row["ask"]),
                        "iv": _safe(round(row["impliedVolatility"] * 100, 2)),
                    }
                    for _, row in put_strikes.head(3).iterrows()
                ]

        if out.get("implied_volatility_call"):
            if out["implied_volatility_call"] > 50:
                out["iv_percentile"] = "high"
                out["risk_note"] = "Options pricing suggests elevated uncertainty"
            elif out["implied_volatility_call"] < 20:
                out["iv_percentile"] = "low"
                out["risk_note"] = "Options pricing suggests calm market"
            else:
                out["iv_percentile"] = "moderate"

        return json.dumps(out)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})