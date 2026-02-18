"""Ensemble: combines and ranks themes from all extractors."""

from __future__ import annotations

import logging
from collections import defaultdict

from stock_themes.config import LLM_MARKET_CAP_THRESHOLD
from stock_themes.models import CompanyProfile, Theme, ThemeResult, ExtractionMethod
from stock_themes.taxonomy.normalizer import ThemeNormalizer
from stock_themes.semantic.filter import semantic_filter, FilterResult

logger = logging.getLogger(__name__)

# Source weights for ensemble scoring
SOURCE_WEIGHTS = {
    ExtractionMethod.LLM: 1.0,
    ExtractionMethod.EMBEDDING: 0.85,
    ExtractionMethod.KEYWORD_NLP: 0.8,
    ExtractionMethod.PATENT: 0.7,
    ExtractionMethod.NEWS: 0.6,
    ExtractionMethod.SIC_MAPPING: 0.5,
    ExtractionMethod.SOCIAL: 0.4,
}

MULTI_SOURCE_BONUS = 0.05  # per additional confirming source
MAX_MULTI_SOURCE_BONUS = 0.15

# Generic terms that are too vague to be actionable investment themes.
# These are filtered out during the merge-and-rank phase.
BLOCKED_THEMES = {
    # Generic corporate terms
    "company", "corporation", "business", "enterprise", "firm", "organization",
    # Generic financial terms
    "stock", "share", "equity", "investment", "revenue", "profit", "earnings",
    "dividend", "capital", "fund", "asset", "portfolio", "growth", "value",
    "market", "trading", "securities", "financial", "fiscal", "monetary",
    # Generic industry terms
    "technology", "industry", "sector", "services", "products", "solutions",
    "operations", "management", "strategy", "innovation", "development",
    "research", "manufacturing", "consumer", "retail", "commercial",
    # Other non-thematic noise
    "global", "international", "domestic", "public", "private",
    "large cap", "mid cap", "small cap", "blue chip",
}


class EnsembleExtractor:
    """Runs all extractors and produces a ranked, deduplicated theme list."""

    def __init__(
        self,
        use_llm: bool = True,
        max_themes: int = 10,
    ):
        self.use_llm = use_llm
        self.max_themes = max_themes
        self.normalizer = ThemeNormalizer()

    def extract(self, profile: CompanyProfile) -> ThemeResult:
        all_themes: list[Theme] = []

        # 1. Run semantic pre-filter (used by embedding matcher and LLM)
        filter_result: FilterResult | None = None
        try:
            filter_result = semantic_filter(profile)
        except Exception as e:
            logger.warning(f"Semantic filter failed for {profile.ticker}: {e}")

        # 2. Run all extractors
        extractors_to_run = self._get_extractors(profile, filter_result)

        for name, extract_fn in extractors_to_run:
            try:
                themes = extract_fn()
                all_themes.extend(themes)
                logger.debug(f"{profile.ticker}: {name} produced {len(themes)} themes")
            except Exception as e:
                logger.warning(f"Extractor {name} failed for {profile.ticker}: {e}")

        # 3. Merge and rank
        ranked = self._merge_and_rank(all_themes)

        return ThemeResult(
            ticker=profile.ticker,
            company_name=profile.name,
            themes=ranked[: self.max_themes],
            profile=profile,
            metadata={
                "sources_used": list({t.source.value for t in all_themes}),
                "total_raw_themes": len(all_themes),
                "chunks_total": filter_result.total_chunks if filter_result else 0,
                "chunks_relevant": filter_result.relevant_count if filter_result else 0,
            },
        )

    def _get_extractors(self, profile: CompanyProfile,
                        filter_result: FilterResult | None) -> list[tuple[str, callable]]:
        """Build list of (name, callable) extractor functions to run."""
        from stock_themes.extraction.sic_mapper import SICMapper
        from stock_themes.extraction.keyword_extractor import KeywordExtractor
        from stock_themes.extraction.patent_mapper import PatentMapper
        from stock_themes.extraction.embedding_matcher import EmbeddingMatcher
        from stock_themes.extraction.news_extractor import NewsExtractor
        from stock_themes.extraction.social_extractor import SocialExtractor
        from stock_themes.extraction.llm_extractor import LLMExtractor

        extractors = [
            ("sic_mapper", lambda: SICMapper().extract(profile)),
            ("keyword", lambda: KeywordExtractor().extract(profile)),
            ("patent", lambda: PatentMapper().extract(profile)),
            ("news", lambda: NewsExtractor().extract(profile)),
            ("social", lambda: SocialExtractor().extract(profile)),
        ]

        # Embedding matcher (uses pre-computed filter result)
        if filter_result is not None:
            extractors.append((
                "embedding",
                lambda: EmbeddingMatcher().extract(profile, filter_result),
            ))

        # LLM extractor (only for stocks above market cap threshold)
        if self.use_llm:
            market_cap = profile.market_cap or 0
            if market_cap >= LLM_MARKET_CAP_THRESHOLD:
                llm = LLMExtractor()
                if llm.is_available():
                    extractors.append((
                        "llm",
                        lambda: llm.extract(profile, filter_result),
                    ))
                else:
                    logger.info(
                        f"{profile.ticker}: skipping LLM (no API key)"
                    )
            else:
                logger.debug(
                    f"{profile.ticker}: skipping LLM "
                    f"(market cap {market_cap:.0f} < {LLM_MARKET_CAP_THRESHOLD:.0f})"
                )

        return extractors

    def _merge_and_rank(self, themes: list[Theme]) -> list[Theme]:
        """Merge themes by normalized name, combine confidences."""
        grouped: dict[str, list[Theme]] = defaultdict(list)

        for theme in themes:
            normalized = self.normalizer.normalize(theme.name)
            grouped[normalized].append(theme)

        merged: list[Theme] = []
        for normalized_name, group in grouped.items():
            if normalized_name in BLOCKED_THEMES:
                logger.debug(f"Filtered generic theme: {normalized_name}")
                continue

            sources = set(t.source for t in group)
            source_bonus = min(
                MAX_MULTI_SOURCE_BONUS,
                MULTI_SOURCE_BONUS * (len(sources) - 1),
            )

            # Weighted average of confidences
            weighted_sum = sum(
                t.confidence * SOURCE_WEIGHTS.get(t.source, 0.5) for t in group
            )
            weighted_count = sum(
                SOURCE_WEIGHTS.get(t.source, 0.5) for t in group
            )
            avg_confidence = weighted_sum / weighted_count if weighted_count else 0

            final_confidence = min(1.0, avg_confidence + source_bonus)

            # Use the best evidence
            best = max(group, key=lambda t: t.confidence)

            # Get canonical category
            category = self.normalizer.get_category(normalized_name)

            merged.append(Theme(
                name=normalized_name,
                confidence=round(final_confidence, 3),
                source=best.source,
                evidence=best.evidence,
                canonical_category=category,
            ))

        merged.sort(key=lambda t: t.confidence, reverse=True)
        return merged
