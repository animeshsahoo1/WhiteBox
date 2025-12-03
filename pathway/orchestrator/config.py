"""
Configuration module for the Risk Assessment MCP Server.
Loads environment variables and initializes shared clients.
"""

import os
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI / LLM Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
OPENAI_MODEL_RISK = os.getenv("OPENAI_MODEL_RISK", "google/gemini-2.0-flash-lite-001")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE_RISK", 0.0))
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS_RISK", 500))

# Server Configuration
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", 9004))

# API URLs (use Docker internal network names)
REPORTS_API_URL = os.getenv("REPORTS_API_URL", "http://unified-api:8000")
BACKTESTING_API_URL = os.getenv("BACKTESTING_API_URL", "http://unified-api:8000/backtesting")

# Serpex API configuration (Web Search)
SERPEX_API_KEY = os.getenv("SERPAPI_API_KEY", "").strip('"').strip("'")
SERPEX_BASE_URL = "https://api.serpex.dev/api/search"

# Trusted trading/finance sites for search prioritization
TRUSTED_TRADING_SITES = [
    "investopedia.com",
    "tradingview.com",
    "github.com",
    "medium.com",
    "seekingalpha.com",
    "quantstart.com",
    "quantconnect.com",
    "backtrader.com",
    "stackoverflow.com",
    "arxiv.org",
    "kaggle.com",
    "babypips.com",
    "thepatternsite.com"
]

# Sites to use for site-specific search enhancement
SITE_SEARCH_DOMAINS = [
    "investopedia.com",
    "tradingview.com",
    "quantstart.com",
    "babypips.com",
    "github.com",
]

# Domains to filter out (low-quality, ads, aggregators, social media)
BLOCKED_DOMAINS = [
    "pinterest.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "instagram.com",
    "tiktok.com",
    "quora.com",  # Often low-quality answers
    "ask.com",
    "answers.com",
    "youtube.com",
    "id.video.search.yahoo.com"
    # Note: We allow google.com/bing.com subdomains (developers.google.com, etc.)
    # but filter search result pages in the parser
]

# Keywords that indicate relevant trading content
TRADING_RELEVANCE_KEYWORDS = [
    "trading", "strategy", "indicator", "backtest", "signal",
    "buy", "sell", "entry", "exit", "stop loss", "take profit",
    "rsi", "macd", "sma", "ema", "bollinger", "moving average",
    "momentum", "trend", "reversal", "divergence", "crossover",
    "profit", "loss", "risk", "reward", "position", "portfolio",
    "stock", "forex", "crypto", "market", "price", "volume",
    "technical analysis", "chart", "pattern", "support", "resistance"
]

# Initialize OpenAI client
openai_client = openai.AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_API_BASE
)


def print_config():
    """Print current configuration for debugging."""
    print(f"MCP Server configured on: {MCP_SERVER_HOST}:{MCP_SERVER_PORT}")
    print(f"Using model: {OPENAI_MODEL_RISK}")
    print(f"Reports API: {REPORTS_API_URL}")
    print(f"Backtesting API: {BACKTESTING_API_URL}")
    print(f"Serpex configured: {'Yes' if SERPEX_API_KEY else 'No (set SERPAPI_API_KEY)'}")
