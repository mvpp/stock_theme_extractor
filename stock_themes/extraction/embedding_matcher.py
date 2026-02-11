"""Embedding-based theme extractor using sentence-transformer similarity scores."""

from __future__ import annotations

from stock_themes.models import CompanyProfile, Theme, ExtractionMethod
from stock_themes.semantic.filter import semantic_filter, FilterResult


class EmbeddingMatcher:
    name = "embedding_matcher"

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold

    def extract(self, profile: CompanyProfile,
                filter_result: FilterResult | None = None) -> list[Theme]:
        """Extract themes based on embedding cosine similarity.

        If filter_result is provided, reuses it to avoid recomputation.
        Otherwise runs semantic_filter from scratch.
        """
        if filter_result is None:
            filter_result = semantic_filter(profile, threshold=self.threshold)

        themes = []
        for theme_name, score in filter_result.matched_themes.items():
            themes.append(Theme(
                name=theme_name,
                confidence=round(score, 3),
                source=ExtractionMethod.EMBEDDING,
                evidence=f"Cosine similarity {score:.3f} against theme embedding",
            ))

        themes.sort(key=lambda t: t.confidence, reverse=True)
        return themes
