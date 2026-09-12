import asyncio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    async with stdio_client(StdioServerParameters(command="python3", args=["server.py"])) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            results = []
            def check(mod, name, ok, detail):
                results.append((mod, name, "PASS" if ok else "FAIL", str(detail)))
            def parsed(res):
                return json.loads(res.content[0].text)

            d = parsed(await s.call_tool("get_quote", {"symbol": "RELIANCE.NS"}))
            check("core", "get_quote", d.get("last_price") is not None, f"₹{d.get('last_price')} ({d.get('change_pct')}%)")
            d = parsed(await s.call_tool("search_symbol", {"query": "hdfc bank"}))
            check("core", "search_symbol", bool(d["results"]) and d["results"][0]["symbol"].startswith("HDFCBANK"),
                  f"→ {[x['symbol'] for x in d['results'][:2]]}")
            d = parsed(await s.call_tool("technical_analysis", {"symbol": "TCS.NS", "period": "1y"}))
            check("core", "technical_analysis", d.get("rsi_14") is not None, f"RSI {d.get('rsi_14')}, {d.get('macd_trend')}")
            d = parsed(await s.call_tool("alpha_vantage_overview", {"symbol": "AAPL"}))
            check("core", "alpha_vantage_overview", (d.get("data") or {}).get("Name") == "Apple Inc.", str((d.get("data") or {}).get("Name")))

            d = parsed(await s.call_tool("analyze_stock", {"symbol": "INFY.NS"}))
            check("analysis", "analyze_stock", bool(d.get("recommendation")) and bool(d.get("data_snapshot")),
                  f"{d.get('recommendation')} ({d.get('score')}), snapshot ok")
            d = parsed(await s.call_tool("analyze_watchlist", {"symbols": "ITC.NS,SBIN.NS"}))
            check("analysis", "analyze_watchlist", len(d["ranked"]) == 2,
                  ", ".join(f"{x['symbol']}:{x['recommendation']}" for x in d["ranked"]))
            d = parsed(await s.call_tool("compare_stocks", {"symbols": "RELIANCE.NS,INFY.NS"}))
            check("analysis", "compare_stocks", len(d["comparison"]) == 2, f"P/E {[c['pe_ratio'] for c in d['comparison']]}")

            d = parsed(await s.call_tool("market_movers", {"market": "india"}))
            n = d.get("nse_movers") or {}
            b = d.get("bse_movers") or {}
            ng, bg = n.get("gainers") or [], b.get("gainers") or []
            check("market", "market_movers", bool(ng) and bool(bg),
                  f"NSE {ng[0]['symbol']} +{ng[0]['change_pct']}% | BSE {bg[0]['company']} +{bg[0]['change_pct']}%" if ng and bg else "no movers data")
            d = parsed(await s.call_tool("stock_news", {"symbol": "INFY.NS", "limit": 3}))
            check("market", "stock_news", len(d.get("news", [])) > 0, f"{len(d['news'])} headlines")
            d = parsed(await s.call_tool("earnings_calendar", {"symbol": "INFY.NS"}))
            check("market", "earnings_calendar", "error" not in d,
                  f"next: {d.get('next_earnings_date', 'n/a')} ({d.get('days_until', '?')} days) | {len(d.get('recent_earnings', []))} past qtrs")

            d = parsed(await s.call_tool("stock_screener", {"symbols": "ITC.NS,SBIN.NS,HDFCBANK.NS,TCS.NS", "min_score": 40}))
            check("screening", "stock_screener", "matches" in d,
                  f"{d.get('n_matches')}/{d.get('n_input')} pass min_score=40: {[m['symbol'] for m in d.get('matches', [])]}")
            d = parsed(await s.call_tool("correlation_analysis", {"symbol": "INFY.NS", "benchmark": "^NSEI", "period": "1y"}))
            check("screening", "correlation_analysis", d.get("correlation") is not None,
                  f"corr {d.get('correlation')}, beta {d.get('beta')}, {d.get('correlation_trend')}")

            d = parsed(await s.call_tool("currency_impact", {"symbol": "RELIANCE.NS"}))
            inr_ret = (d.get("inr") or {}).get("return_pct")
            usd_ret = (d.get("usd") or {}).get("return_pct")
            check("fundamentals", "currency_impact", inr_ret is not None,
                  f"INR {inr_ret}% vs USD {usd_ret}% ({d.get('interpretation')})")
            d = parsed(await s.call_tool("dividend_calendar", {"symbol": "ITC.NS"}))
            check("fundamentals", "dividend_calendar", "error" not in d,
                  f"yield {d.get('dividend_yield')}%, recent divs: {len(d.get('recent_dividends', []))}")

            d = parsed(await s.call_tool("options_data", {"symbol": "AAPL"}))
            check("derivatives", "options_data", bool(d.get("expiration_dates")),
                  f"{len(d.get('expiration_dates', []))} expirations, IV call {d.get('implied_volatility_call')}, sentiment {d.get('sentiment')}")

            d = parsed(await s.call_tool("sector_mapping", {"symbol": "TCS.NS"}))
            check("classification", "sector_mapping", d.get("sector") is not None,
                  f"{d.get('sector')} / {d.get('industry')}, {len(d.get('peers', []))} peers")

            d = parsed(await s.call_tool("fii_dii_flows", {"symbol": "RELIANCE.NS"}))
            check("flows", "fii_dii_flows", "error" not in d,
                  f"{len(d.get('institutional_holders', []))} inst. holders, {len(d.get('mutual_fund_holders', []))} MF holders")

            d = parsed(await s.call_tool("log_decision", {"symbol": "HDFCBANK.NS", "action": "BUY",
                                          "rationale": "modular refactor e2e test", "score": 55.0}))
            price = (d.get("decision") or {}).get("price_at_decision")
            check("journal", "log_decision", d.get("logged") is True, f"HDFCBANK @ ₹{price}")
            d = parsed(await s.call_tool("review_decisions", {"symbol": "HDFCBANK.NS"}))
            check("journal", "review_decisions", bool(d.get("review")),
                  f"{d.get('n_open')} open, outcome: {(d.get('review') or [{}])[0].get('outcome')}")
            d = parsed(await s.call_tool("analyst_reports", {"symbol": "SBIN.NS"}))
            check("journal", "analyst_reports", set(d.get("reports", {})) == {"fundamentals", "technical", "sentiment"},
                  "3 timestamped reports")

            pr = await s.get_prompt("bull_bear_debate", {"symbol": "TCS.NS"})
            check("prompts", "bull_bear_debate", "TCS.NS" in pr.messages[0].content.text, "renders with symbol")

            print(f"\n{'MODULE':<14} {'TOOL':<24} {'RESULT':<6} DETAIL")
            print("=" * 100)
            for mod, name, res, detail in results:
                print(f"{mod:<14} {name:<24} {res:<6} {detail}")
            print("=" * 100)
            fails = [x for x in results if x[2] == "FAIL"]
            print(f"TOTAL: {len(results) - len(fails)}/{len(results)} passed" +
                  (f" — FAILURES: {[x[1] for x in fails]}" if fails else ""))

asyncio.run(main())
