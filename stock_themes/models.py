from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class ExtractionMethod(Enum):
    SIC_MAPPING = "sic"
    KEYWORD_NLP = "keyword"
    PATENT = "patent"
    EMBEDDING = "embedding"
    NEWS = "news"
    SOCIAL = "social"
    LLM = "llm"


@dataclass
class CompanyProfile:
    """Unified company data merged from all providers."""

    ticker: str
    name: str
    sector: str | None = None
    industry: str | None = None
    sic_code: str | None = None
    market_cap: float | None = None
    exchange: str | None = None
    employees: int | None = None
    website: str | None = None
    # Text sources
    business_summary: str | None = None  # Yahoo Finance short summary
    business_description: str | None = None  # SEC 10-K/Q/S-1 full text
    risk_factors: str | None = None  # SEC Item 1A
    # Patent data
    patent_titles: list[str] = field(default_factory=list)
    patent_cpc_codes: list[str] = field(default_factory=list)
    patent_count: int = 0
    # News data
    news_themes: list[str] = field(default_factory=list)  # GDELT theme codes
    news_titles: list[str] = field(default_factory=list)
    news_tone: float | None = None  # average tone from GDELT
    # Social data
    social_text: str | None = None  # aggregated StockTwits messages
    social_sentiment: dict | None = None  # {"bullish": 65, "bearish": 35}
    # Metadata
    data_sources: list[str] = field(default_factory=list)


@dataclass
class Theme:
    """A single extracted theme with metadata."""

    name: str
    confidence: float  # 0.0 to 1.0
    source: ExtractionMethod
    evidence: str | None = None
    canonical_category: str | None = None


@dataclass
class ThemeResult:
    """Final output for a ticker."""

    ticker: str
    company_name: str
    themes: list[Theme]
    profile: CompanyProfile
    metadata: dict = field(default_factory=dict)

    def theme_names(self, min_confidence: float = 0.0) -> list[str]:
        return [t.name for t in self.themes if t.confidence >= min_confidence]


@dataclass
class SocialMessage:
    """A single social media message."""

    ticker: str
    source: str  # "stocktwits", "reddit", etc.
    message_id: str | None
    body: str
    sentiment: str | None  # "bullish", "bearish", or None (neutral)
    created_at: datetime | None = None
