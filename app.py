"""Shared FastMCP instance for stock_market_mcp.

Tools and prompts import `mcp` from here and register via decorators.
server.py imports the tool modules (which triggers registration) and runs the server.
Keep this module free of tool imports — server.py owns those — to avoid circular imports.
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("stock_market_mcp")
