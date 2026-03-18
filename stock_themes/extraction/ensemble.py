"""Ensemble: combines and ranks themes from all extractors."""

from __future__ import annotations

import logging
from collections import defaultdict

from stock_themes.config import LLM_MARKET_CAP_THRESHOLD
from stock_themes.models import CompanyProfile, Theme, OpenTheme, ThemeResult, ExtractionMethod
from stock_themes.taxonomy.normalizer import ThemeNormalizer
from stock_themes.taxonomy.tree import get_theme_tree
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
        investor_changes: dict | None = None,
    ):
        self.use_llm = use_llm
        self.max_themes = max_themes
        self.normalizer = ThemeNormalizer()
        self._investor_changes = investor_changes or {}

    def extract(self, profile: CompanyProfile) -> ThemeResult:
        all_themes: list[Theme] = []
        all_open_themes: list[OpenTheme] = []

        # 1. Run semantic pre-filter (used by embedding matcher)
        filter_result: FilterResult | None = None
        try:
            filter_result = semantic_filter(profile)
        except Exception as e:
            logger.warning(f"Semantic filter failed for {profile.ticker}: {e}")

        # 2. Run non-LLM extractors
        extractors_to_run = self._get_extractors(profile, filter_result)

        for name, extract_fn in extractors_to_run:
            try:
                themes = extract_fn()
                all_themes.extend(themes)
                logger.debug(f"{profile.ticker}: {name} produced {len(themes)} themes")
            except Exception as e:
                logger.warning(f"Extractor {name} failed for {profile.ticker}: {e}")

        # 3. Run LLM extractor (returns canonical + open themes)
        if self.use_llm:
            llm_canonical, llm_open = self._run_llm(profile)
            all_themes.extend(llm_canonical)
            all_open_themes.extend(llm_open)

        # 4. Run narrative extractor (returns open themes only)
        narrative_open = self._run_narrative(profile)
        all_open_themes.extend(narrative_open)

        # 4.5 Run investor holdings extractor (optional, 13F)
        investor_open = self._run_investor(profile)
        all_open_themes.extend(investor_open)

        # 5. Apply time decay to NEWS-sourced canonical themes
        if profile.dated_articles:
            from stock_themes.extraction.time_decay import freshness_score
            freshness = freshness_score(profile.dated_articles)
            for theme in all_themes:
                if theme.source == ExtractionMethod.NEWS:
                    theme.confidence = round(theme.confidence * freshness, 3)

        # 6. Merge and rank canonical themes
        ranked = self._merge_and_rank(all_themes)

        # 7. Deduplicate open themes
        deduped_open = self._dedup_open_themes(all_open_themes)

        return ThemeResult(
            ticker=profile.ticker,
            company_name=profile.name,
            themes=ranked[: self.max_themes],
            profile=profile,
            open_themes=deduped_open,
            metadata={
                "sources_used": list({t.source.value for t in all_themes}),
                "total_raw_themes": len(all_themes),
                "total_open_themes": len(deduped_open),
                "chunks_total": filter_result.total_chunks if filter_result else 0,
                "chunks_relevant": filter_result.relevant_count if filter_result else 0,
            },
        )

    def _run_llm(self, profile: CompanyProfile) -> tuple[list[Theme], list[OpenTheme]]:
        """Run LLM extractor if eligible. Returns (canonical, open) themes."""
        market_cap = profile.market_cap or 0
        if market_cap < LLM_MARKET_CAP_THRESHOLD:
            logger.debug(
                f"{profile.ticker}: skipping LLM "
                f"(market cap {market_cap:.0f} < {LLM_MARKET_CAP_THRESHOLD:.0f})"
            )
            return [], []

        from stock_themes.extraction.llm_extractor import LLMExtractor
        llm = LLMExtractor()
        if not llm.is_available():
            logger.info(f"{profile.ticker}: skipping LLM (no API key)")
            return [], []

        try:
            return llm.extract(profile)
        except Exception as e:
            logger.warning(f"LLM extractor failed for {profile.ticker}: {e}")
            return [], []

    def _run_narrative(self, profile: CompanyProfile) -> list[OpenTheme]:
        """Run narrative extractor if LLM is available and news exists."""
        if not self.use_llm or (not profile.news_titles and not profile.dated_articles):
            return []

        from stock_themes.extraction.narrative_extractor import NarrativeExtractor
        extractor = NarrativeExtractor()
        if not extractor.is_available():
            return []

        try:
            return extractor.extract(profile)
        except Exception as e:
            logger.warning(f"Narrative extractor failed for {profile.ticker}: {e}")
            return []

    def _run_investor(self, profile: CompanyProfile) -> list[OpenTheme]:
        """Run investor holdings extractor if 13F data is available."""
        if not self._investor_changes:
            return []

        try:
            from stock_themes.extraction.investor_extractor import InvestorHoldingExtractor
            extractor = InvestorHoldingExtractor(self._investor_changes)
            return extractor.extract(profile)
        except ImportError:
            return []
        except Exception as e:
            logger.warning(f"Investor extractor failed for {profile.ticker}: {e}")
            return []

    def _get_extractors(self, profile: CompanyProfile,
                        filter_result: FilterResult | None) -> list[tuple[str, callable]]:
        """Build list of (name, callable) extractor functions to run.

        Does NOT include LLM or narrative — those are handled separately
        because they return different types.
        """
        from stock_themes.extraction.sic_mapper import SICMapper
        from stock_themes.extraction.keyword_extractor import KeywordExtractor
        from stock_themes.extraction.patent_mapper import PatentMapper
        from stock_themes.extraction.embedding_matcher import EmbeddingMatcher
        from stock_themes.extraction.news_extractor import NewsExtractor
        from stock_themes.extraction.social_extractor import SocialExtractor

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

        return extractors

    def _dedup_open_themes(self, open_themes: list[OpenTheme]) -> list[OpenTheme]:
        """Deduplicate open themes by exact text match.

        Keeps the entry with highest confidence for each unique text.
        """
        if not open_themes:
            return []

        best: dict[str, OpenTheme] = {}
        for ot in open_themes:
            key = ot.text.strip().lower()
            if key not in best or ot.confidence > best[key].confidence:
                best[key] = ot

        result = sorted(best.values(), key=lambda t: t.confidence, reverse=True)
        return result

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

        # Hierarchical family pooling: keep deepest 3 per family, boost confidence
        merged = self._pool_family_confidence(merged)

        # Clinical stage dedup: keep only the most advanced stage
        CLINICAL_STAGES = [
            "preclinical", "phase 1", "phase 2", "phase 3",
            "nda/bla filed", "fda approved",
        ]
        stage_themes = {t.name: t for t in merged if t.name in CLINICAL_STAGES}
        if len(stage_themes) > 1:
            # Find the most advanced stage present
            best_stage = max(stage_themes, key=lambda s: CLINICAL_STAGES.index(s))
            for stage_name in stage_themes:
                if stage_name != best_stage:
                    merged.remove(stage_themes[stage_name])
                    logger.debug(
                        f"Clinical stage dedup: dropped '{stage_name}' "
                        f"(keeping '{best_stage}')"
                    )

        merged.sort(key=lambda t: t.confidence, reverse=True)
        return merged

    def _pool_family_confidence(self, merged: list[Theme]) -> list[Theme]:
        """Pool confidence across themes in the same family.

        For each family (shared root ancestor in the theme tree):
        - Sort themes by depth (most specific first), then confidence
        - Keep the deepest 3 themes per family
        - Boost their confidence using sibling evidence + breadth bonus
        - Drop parent/shallower themes (their evidence is absorbed)

        Themes not in the tree (orphans) pass through unchanged.
        """
        tree = get_theme_tree()
        if not tree.has_themes():
            return merged

        # Group by family (root ancestor)
        families: dict[str, list[Theme]] = defaultdict(list)
        orphans: list[Theme] = []

        for theme in merged:
            family = tree.get_family(theme.name)
            if family is not None:
                families[family].append(theme)
            else:
                orphans.append(theme)

        result: list[Theme] = list(orphans)

        for family_name, family_themes in families.items():
            if len(family_themes) == 1:
                result.append(family_themes[0])
                continue

            # Breadth bonus: more family members found = stronger signal
            # 0.03 per additional member, capped at 0.10
            breadth_bonus = min(0.10, 0.03 * (len(family_themes) - 1))

            # Sort by depth desc (most specific first), then confidence desc
            family_themes.sort(
                key=lambda t: (tree.get_depth(t.name), t.confidence),
                reverse=True,
            )

            # Keep deepest 3 leaves per root
            kept = family_themes[:3]
            dropped = family_themes[3:]

            for theme in kept:
                # Sibling/parent corroboration: 30% weight from avg sibling conf
                siblings = [t.confidence for t in family_themes if t.name != theme.name]
                if siblings:
                    avg_sibling = sum(siblings) / len(siblings)
                    # Scale boost by how many siblings exist (breadth_bonus / max)
                    sibling_boost = 0.3 * avg_sibling * (breadth_bonus / 0.10)
                else:
                    sibling_boost = 0.0

                boosted = min(1.0, theme.confidence + sibling_boost + breadth_bonus)

                result.append(Theme(
                    name=theme.name,
                    confidence=round(boosted, 3),
                    source=theme.source,
                    evidence=theme.evidence,
                    canonical_category=theme.canonical_category,
                ))

            if dropped:
                dropped_names = [t.name for t in dropped]
                kept_names = [t.name for t in kept]
                logger.debug(
                    f"Family '{family_name}': kept {kept_names}, "
                    f"dropped {dropped_names} (evidence absorbed)"
                )

        return result
