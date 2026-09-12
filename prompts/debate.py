"""Bull-bear debate prompt (TradingAgents-style, India-focused)."""
from app import mcp


@mcp.prompt()
def bull_bear_debate(symbol: str) -> str:
    """Structured bull-vs-bear debate workflow for a stock (TradingAgents-style, India-focused)."""
    return f"""You are conducting a structured investment debate for {symbol} (NSE/BSE). Follow these steps:

1. GATHER: Call the analyst_reports tool for {symbol}. Treat every number in the reports as verified data — do not use figures from memory.
2. BULL CASE: Argue the strongest honest case FOR the stock, citing only the snapshot data (and further tool calls if needed).
3. BEAR CASE: Argue the strongest honest case AGAINST it, same grounding rules. Steelman both sides.
4. RISK CHECK: List what would falsify the bull case, what would falsify the bear case, position-size and liquidity considerations for an NSE/BSE large-cap, and upcoming events (earnings, ex-dividend) that change the risk.
5. DECISION: Give BUY/HOLD/SELL with a 0-100 score and a confidence level (low/medium/high), stating the time horizon the call is valid for.
6. JOURNAL: Call log_decision with the final action, score, and a one-paragraph rationale.

Rules: every claim must trace to the data snapshot or a fresh tool call. If data is missing, say so instead of filling gaps from memory. This is educational analysis, not financial advice — say so in the final answer."""
