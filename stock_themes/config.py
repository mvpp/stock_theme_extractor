import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API keys
SEC_EDGAR_EMAIL = os.environ.get("SEC_EDGAR_EMAIL", "stock_themes@example.com")

# HuggingFace token (optional — speeds up model downloads, avoids rate limits)
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# PatentsView API key (required for patent data)
PATENTSVIEW_API_KEY = os.environ.get("PATENTSVIEW_API_KEY", "")

# StockTwits access token (API currently frozen — set when available)
STOCKTWITS_ACCESS_TOKEN = os.environ.get("STOCKTWITS_ACCESS_TOKEN", "")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DIR = Path.home() / ".cache" / "stock_themes"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# LLM provider presets (all OpenAI-compatible)
LLM_PROVIDERS = {
    "kimi": {
        "base_url": "https://api.moonshot.ai/v1",
        "model": "kimi-k2.5",
        "env_key": "MOONSHOT_API_KEY",
    },
    "minimax": {
        "base_url": "https://api.minimaxi.chat/v1",
        "model": "MiniMax-Text-01",
        "env_key": "MINIMAX_API_KEY",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash-250414",
        "env_key": "GLM_API_KEY",
    },
}

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "kimi")
_provider = LLM_PROVIDERS[LLM_PROVIDER]
LLM_API_KEY = os.environ.get(_provider["env_key"], "")
LLM_BASE_URL = _provider["base_url"]
LLM_MODEL = _provider["model"]
LLM_MARKET_CAP_THRESHOLD = 1e9  # $1B — stocks above this get LLM extraction

# Semantic filter settings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = 0.6
CHUNK_SIZE_WORDS = 200

# Batch processing
BATCH_SIZE = 50
LLM_DELAY_SECONDS = 0.5  # delay between LLM calls
SEC_RATE_LIMIT_DELAY = 0.15  # ~7 req/sec, under 10 req/sec SEC limit
YAHOO_RATE_LIMIT_DELAY = 0.5

# Browser-like User-Agent for non-yfinance HTTP requests
# (yfinance itself uses curl_cffi with impersonate="chrome" internally)
FAKE_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Cache TTLs (hours)
YAHOO_CACHE_TTL_HOURS = 24
SEC_10K_CACHE_TTL_HOURS = 168  # 1 week
SEC_10Q_CACHE_TTL_HOURS = 24
PATENT_CACHE_TTL_HOURS = 168
NEWS_CACHE_TTL_HOURS = 12
