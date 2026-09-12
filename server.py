"""
stock_market_mcp — Stock Analysis MCP Server (entrypoint).

Analyzes stocks and returns BUY / HOLD / SELL style assessments using:
  1. Yahoo Finance (via yfinance) — free, no API key required
  2. nseindia.com / bsedata — exchange-native NSE/BSE market movers
  3. Alpha Vantage (optional) — extra market data when ALPHA_VANTAGE_API_KEY is set
  4. MongoDB — decision journal (JSON-file fallback)

Structure:
  app.py               shared FastMCP instance
  config.py            env/config constants
  utils/helpers.py     shared helpers (_safe, RSI, MACD, ...)
  tools/*.py           tool modules (registered via @mcp.tool decorators)
  prompts/debate.py    the bull_bear_debate prompt

Run:  python server.py        (stdio MCP server)
"""
import app  # noqa: F401 — creates the shared FastMCP instance
from app import mcp

# Importing these modules registers their @mcp.tool() / @mcp.prompt() handlers
import tools  # noqa: F401
import prompts  # noqa: F401

if __name__ == "__main__":
    mcp.run()  # stdio transport
