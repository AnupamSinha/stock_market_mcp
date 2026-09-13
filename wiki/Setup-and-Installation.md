# Setup and Installation

## Prerequisites

- Python 3.10+
- `pip`
- An MCP client such as ZCode, Claude Desktop, or another MCP-compatible host
- Optional: Alpha Vantage API key for `alpha_vantage_overview`
- Optional: MongoDB for the decision journal

## Install

```bash
git clone https://github.com/AnupamSinha/stock_market_mcp.git
cd stock_market_mcp
pip install -r requirements.txt
```

The project dependencies are intentionally lightweight:

- `mcp`
- `yfinance`
- `bsedata`

If macOS SSL problems appear during package installation, run:

```bash
pip install certifi
```

The server automatically uses `certifi` when it is installed.

## Optional configuration

Create a `.env` file in the project root (or export the same variables):

```bash
ALPHA_VANTAGE_API_KEY=your_key_here
ALPHA_VANTAGE_BASE_URL=https://www.alphavantage.co/query
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=stock_data
```

The server loads `.env` automatically at startup. Any environment variables already present take precedence.

Aside from `alpha_vantage_overview`, the rest of the tools work with zero mandatory configuration.

## Run the server

This project is a stdio MCP server: your client launches it. You normally do not run it by hand except for debugging.

```bash
python3 server.py
```

## MCP client configuration

### ZCode

Add the following to `~/.zcode/cli/config.json`:

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

Use absolute paths. Restart the client or start a fresh session after adding the server.

## Verify the connection

```bash
python3 - <<'EOF'
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python3", args=["server.py"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            prompts = await s.list_prompts()
            print("TOOLS:", [t.name for t in tools.tools])
            print("PROMPTS:", [p.name for p in prompts.prompts])

asyncio.run(main())
EOF
```

Expected output: the tool names for all 20 registered tools, plus `bull_bear_debate`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Tools do not appear | Start a new MCP session; verify the absolute path to `server.py` |
| `No module named 'mcp'` | `pip install -r requirements.txt` |
| SSL errors | `pip install certifi` |
| Alpha Vantage says key missing | Check `.env` or export `ALPHA_VANTAGE_API_KEY` |
| Journal not writing | Confirm MongoDB or allow the JSON fallback |
