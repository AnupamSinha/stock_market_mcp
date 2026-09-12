"""Flow tools: fii_dii_flows."""
import json
from datetime import datetime, timedelta

import yfinance as yf

from utils.helpers import _safe

from app import mcp


@mcp.tool()
def fii_dii_flows(symbol: str = "", period: str = "1m") -> str:
    """Per-stock institutional holders and insider activity."""
    try:
        t = yf.Ticker(symbol) if symbol else None
        out = {"period": period, "source": "Yahoo Finance (yfinance)"}

        if symbol:
            holders = (
                t.institutional_holders if hasattr(t, "institutional_holders") else None
            )

            if holders is not None and not holders.empty:
                out["institutional_holders"] = [
                    {
                        "holder": row.get("Holder", str(row.get("name", ""))),
                        "shares": _safe(row.get("Shares")),
                        "value": _safe(row.get("Value")),
                        "pct_held": (
                            _safe(round(row.get("pctOfShares", 0) * 100, 2))
                            if row.get("pctOfShares")
                            else None
                        ),
                        "change_pct": (
                            _safe(round(row.get("Change", 0) * 100, 2)) if row.get("Change") else None
                        ),
                    }
                    for _, row in holders.iterrows()
                ]

            mfh = t.mutualfund_holders if hasattr(t, "mutualfund_holders") else None
            if mfh is not None and not mfh.empty:
                out["mutual_fund_holders"] = [
                    {
                        "holder": row.get("Holder", str(row.get("name", ""))),
                        "shares": _safe(row.get("Shares")),
                        "value": _safe(row.get("Value")),
                        "pct_held": (
                            _safe(round(row.get("pctOfShares", 0) * 100, 2))
                            if row.get("pctOfShares")
                            else None
                        ),
                    }
                    for _, row in mfh.head(10).iterrows()
                ]

            insider = (
                t.insider_transactions if hasattr(t, "insider_transactions") else None
            )
            if insider is not None and not insider.empty:
                try:
                    recent = insider[
                        insider["Date"]
                        > (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
                    ]
                    out["insider_activity"] = [
                        {
                            "date": str(row.get("Date"))[:10] if row.get("Date") else None,
                            "type": row.get("Transaction"),
                            "shares": _safe(row.get("Shares")),
                            "value": _safe(row.get("Value")),
                        }
                        for _, row in recent.head(5).iterrows()
                    ]
                except Exception:
                    out["insider_activity"] = [
                        {
                            "date": str(row.get("Date"))[:10] if row.get("Date") else None,
                            "type": row.get("Transaction"),
                            "shares": _safe(row.get("Shares")),
                            "value": _safe(row.get("Value")),
                        }
                        for _, row in insider.head(5).iterrows()
                    ]

            if not out.get("institutional_holders"):
                out["note"] = "Limited institutional holder data available for this symbol"
        else:
            out[
                "note"
            ] = "Market-wide FII/DII flows require paid NSE API. For stock-specific holders, provide a symbol."
            out["alternative"] = "Use sector_mapping + compare_stocks for sector-level analysis"

        return json.dumps(out)
    except Exception as e:
        return json.dumps({"symbol": symbol, "error": str(e)})