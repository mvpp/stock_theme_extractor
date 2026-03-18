"""API configuration — environment-based, no dependency on stock_themes."""

import os

DB_PATH = os.environ.get("STOCK_THEMES_DB", "stock_themes.db")
TAXONOMY_YAML_PATH = os.environ.get("TAXONOMY_YAML_PATH", "taxonomy.yaml")

# Quality thresholds (mirrors stock_themes/config.py unified section)
QUALITY_WEIGHTS = {"confidence": 0.6, "distinctiveness": 0.4}
THRESHOLDS = {
    "llm": {"min_confidence": 0.5, "min_distinctiveness": 0.15, "min_quality": 0.35},
    "narrative": {"min_confidence": 0.6, "min_distinctiveness": 0.10, "min_quality": 0.40},
}
MAX_MAPPED_SIMILARITY = 0.85
PROMOTION = {
    "min_stock_count": 5,
    "min_avg_confidence": 0.6,
    "min_avg_distinctiveness": 0.3,
    "min_avg_quality": 0.45,
}

# Tradeability score component weights (must sum to 1.0)
TRADEABILITY_WEIGHTS = {
    "relevance": 0.25,
    "uniqueness": 0.15,
    "recency": 0.15,
    "corroboration": 0.20,
    "narrative_intensity": 0.15,
    "taxonomy_depth": 0.10,
}

# Total possible source types for corroboration calculation
ALL_SOURCE_TYPES = ["llm", "narrative", "13f", "patent", "news", "sic", "social"]
