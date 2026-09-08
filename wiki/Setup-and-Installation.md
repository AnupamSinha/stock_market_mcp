# Setup and Installation

## Prerequisites

- Python 3.10+ (tested on 3.13, macOS/Linux)
- pip
- An MCP client (ZCode, Claude Desktop, etc.)
- Optional: Alpha Vantage API key (free at https://www.alphavantage.co/support/#api-key)
- Optional: MongoDB (for the decision journal; falls back to a local JSON file)

## Install

```bash
git clone https://github.com/AnupamSinha/stock_market_mcp.git
cd stock_market_mcp
pip install -r requirements.txt
```

Dependencies: `mcp` (the MCP SDK) and `yfinance`. macOS users: if HTTPS calls fail
with an SSL error, `pip install certifi` (the server uses it automatically when present).

## Configure (optional)

Create `.env` in the project root (loaded automatically; real env vars take precedence):

```bash
ALPHA_VANTAGE_API_KEY=your_key_here
# Optional overrides:
ALPHA_VANTAGE_BASE_URL=https://www.alphavantage.co/query
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=stock_data
```

Everything except `alpha_vantage_overview` works with **zero configuration**.

## Run

`server.py` runs on **stdio** — you don't start it by hand; your MCP client launches it.

## MCP client configuration

### ZCode — `~/.zcode/cli/config.json` (user scope)

```json
{
  "mcp": {
    "servers": {
      "stock_market_mcp": {
        "command": "python3",
        "args": ["/absolute/path/to/stock_market_mcp/server.py"]
      }
    }
  }
}
```

### Claude Desktop

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "stock_market_mcp": {
      "command": "python3",
      "args": ["/absolute/path/to/stock_market_mcp/server.py"]
    }
  }
}
```

Restart the client and start a **new conversation**. Tools appear as `mcp__stock_market_mcp__*`.

## Verify

```bash
python3 - <<'EOF'
import asyncio, json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    async with stdio_client(StdioServerParameters(command="python3", args=["server.py"])) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print("TOOLS:", [t.name for t in (await s.list_tools()).tools])
            print("PROMPTS:", [p.name for p in (await s.list_prompts()).prompts])

asyncio.run(main())
EOF
```

Expected: 11 tool names and `['bull_bear_debate']`.
