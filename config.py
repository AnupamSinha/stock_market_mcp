"""Configuration for stock_market_mcp (loaded once; env vars win over .env)."""
import os


def _load_env(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")):
    """Minimal .env loader: KEY=VALUE lines are set as env vars (not overriding existing)."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass


_load_env()

ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
ALPHA_VANTAGE_BASE_URL = os.environ.get("ALPHA_VANTAGE_BASE_URL", "https://www.alphavantage.co/query")
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.environ.get("MONGODB_DB_NAME", "stock_data")
JOURNAL_COLLECTION = "decision_journal"

MOVERS_TTL = 600  # seconds — NSE/BSE movers scrape exchange sites; cache hard to stay polite
