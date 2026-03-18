import os
from pathlib import Path

import yaml
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))

# --- Load settings.yaml ---
_settings_path = Path(__file__).parent / "settings.yaml"
with open(_settings_path) as _f:
    _cfg = yaml.safe_load(_f)

# --- Secrets from .env ---
SEC_EDGAR_EMAIL = os.environ.get("SEC_EDGAR_EMAIL", "stock_themes@example.com")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
PATENTSVIEW_API_KEY = os.environ.get("PATENTSVIEW_API_KEY", "")
STOCKTWITS_ACCESS_TOKEN = os.environ.get("STOCKTWITS_ACCESS_TOKEN", "")
MARKETAUX_API_TOKEN = os.environ.get("MARKETAUX_API_TOKEN", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
WEBSHARE_USERNAME = os.environ.get("WEBSHARE_USERNAME", "")
WEBSHARE_PASSWORD = os.environ.get("WEBSHARE_PASSWORD", "")

# --- Derived: rotating proxy URL ---
_proxy = _cfg["proxy"]
PROXY_URL = (
    f"http://{WEBSHARE_USERNAME}:{WEBSHARE_PASSWORD}@{_proxy['host']}:{_proxy['port']}"
    if WEBSHARE_USERNAME and WEBSHARE_PASSWORD
    else ""
)

# --- Paths ---
PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DIR = Path(_cfg["cache_dir"]).expanduser()
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# --- LLM ---
_llm = _cfg["llm"]
LLM_PROVIDERS = _llm["providers"]
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", _llm["default_provider"])
_provider = LLM_PROVIDERS[LLM_PROVIDER]
LLM_API_KEY = os.environ.get(_provider["env_key"], "")
LLM_BASE_URL = _provider["base_url"]
LLM_MODEL = _provider["model"]
LLM_MARKET_CAP_THRESHOLD = _llm["market_cap_threshold"]
LLM_DELAY_SECONDS = _llm["delay_seconds"]
LLM_MAX_INPUT_CHARS = _llm["max_input_chars"]
LLM_SIMILARITY_THRESHOLD = _llm["similarity_threshold"]
LLM_HEAD_RATIO = _llm.get("head_ratio", 0.7)

# --- Semantic filter ---
_semantic = _cfg["semantic"]
EMBEDDING_MODEL = _semantic["embedding_model"]
SIMILARITY_THRESHOLD = _semantic["similarity_threshold"]
CHUNK_SIZE_WORDS = _semantic["chunk_size_words"]

# --- News providers ---
_news = _cfg["news"]
GDELT_API_URL = _news["gdelt"]["api_url"]
GDELT_MAX_RECORDS = str(_news["gdelt"]["max_records"])
GDELT_TIMESPAN = _news["gdelt"]["timespan"]
MARKETAUX_API_URL = _news["marketaux"]["api_url"]
MARKETAUX_LIMIT = _news["marketaux"]["limit"]
MARKETAUX_LANGUAGE = _news["marketaux"]["language"]

# --- Rate limits ---
_rates = _cfg["rate_limits"]
SEC_RATE_LIMIT_DELAY = _rates["sec_edgar"]
YAHOO_RATE_LIMIT_DELAY = _rates["yahoo_finance"]

# --- Cache TTLs (hours) ---
_ttl = _cfg["cache_ttl"]
YAHOO_CACHE_TTL_HOURS = _ttl["yahoo"]
SEC_10K_CACHE_TTL_HOURS = _ttl["sec_10k"]
SEC_10Q_CACHE_TTL_HOURS = _ttl["sec_10q"]
PATENT_CACHE_TTL_HOURS = _ttl["patent"]
NEWS_CACHE_TTL_HOURS = _ttl["news"]

# --- Corpus TF-IDF ---
_corpus = _cfg["corpus"]
CORPUS_REBUILD_EVERY_N = _corpus["rebuild_every_n_tickers"]
CORPUS_NGRAM_RANGE = _corpus["ngram_range"]
CORPUS_MAX_FEATURES = _corpus["max_features"]
CORPUS_MIN_DF = _corpus["min_df"]
CORPUS_MAX_DF = _corpus["max_df"]

# --- Narrative ---
_narrative = _cfg["narrative"]
NARRATIVE_MAX_TITLES = _narrative["max_titles"]
NARRATIVE_MAX_THEMES = _narrative["max_themes"]

# --- Unified query layer ---
_unified = _cfg.get("unified", {})
UNIFIED_QUALITY_WEIGHTS = _unified.get("quality_weights", {"confidence": 0.6, "distinctiveness": 0.4})
UNIFIED_THRESHOLDS = _unified.get("thresholds", {
    "llm": {"min_confidence": 0.5, "min_distinctiveness": 0.15, "min_quality": 0.35},
    "narrative": {"min_confidence": 0.6, "min_distinctiveness": 0.10, "min_quality": 0.40},
})
UNIFIED_MAX_MAPPED_SIM = _unified.get("max_mapped_similarity", 0.85)
UNIFIED_PROMOTION = _unified.get("promotion", {
    "min_stock_count": 5, "min_avg_confidence": 0.6,
    "min_avg_distinctiveness": 0.3, "min_avg_quality": 0.45,
})

# --- Time decay ---
_decay = _cfg.get("time_decay", {})
DECAY_FRESH_DAYS = _decay.get("fresh_days", 30)
DECAY_STALE_DAYS = _decay.get("stale_days", 365)

# --- Company news ---
_company_news = _cfg.get("company_news", {})
COMPANY_NEWS_MAX_ARTICLES = _company_news.get("max_articles", 20)
COMPANY_NEWS_MAX_DEPTH = _company_news.get("max_depth", 2)
COMPANY_NEWS_RATE_LIMIT = _company_news.get("rate_limit_seconds", 1.0)
COMPANY_NEWS_CACHE_TTL_HOURS = _company_news.get("cache_ttl_hours", 48)
COMPANY_NEWS_MARKDOWN_SERVICES = _company_news.get("markdown_services", [
    "https://markdown.new/{url}",
    "https://defuddle.md/{url}",
    "https://r.jina.ai/{url}",
])
COMPANY_NEWS_SITEMAP_KEYWORDS = _company_news.get(
    "sitemap_keywords", ["news", "press", "media", "blog", "release", "announcement"]
)
COMPANY_NEWS_COMMON_PATHS = _company_news.get(
    "common_paths", ["/news", "/newsroom", "/press-releases", "/media", "/blog", "/investors/news"]
)

# --- 13F investor holdings (optional) ---
_thirteen_f = _cfg.get("thirteen_f", {})
THIRTEEN_F_ENABLED = _thirteen_f.get("enabled", False)
THIRTEEN_F_INVESTORS_FILE = _thirteen_f.get("investors_file", "investors.yaml")
THIRTEEN_F_CACHE_TTL_DAYS = _thirteen_f.get("cache_ttl_days", 7)
THIRTEEN_F_MIN_POSITION_VALUE = _thirteen_f.get("min_position_value", 1000)
THIRTEEN_F_SIGNIFICANT_PCT = _thirteen_f.get("change_thresholds", {}).get("significant_pct", 50)

# --- Batch processing ---
BATCH_SIZE = _cfg["batch_size"]

# --- User-Agent ---
FAKE_USER_AGENT = _cfg["user_agent"]
