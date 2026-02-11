"""GDELT news theme → investment theme mapper."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from stock_themes.models import CompanyProfile, Theme, ExtractionMethod


class NewsExtractor:
    name = "news_extractor"

    def __init__(self):
        mapping_path = Path(__file__).parent.parent / "taxonomy" / "gdelt_mapping.json"
        with open(mapping_path) as f:
            self._mapping: dict[str, str] = json.load(f)

    def extract(self, profile: CompanyProfile) -> list[Theme]:
        if not profile.news_themes:
            return []

        # Map GDELT themes to our canonical themes
        theme_counts: Counter = Counter()
        for gdelt_theme in profile.news_themes:
            gdelt_theme = gdelt_theme.strip().upper()
            # Try exact match, then prefix match
            if gdelt_theme in self._mapping:
                theme_counts[self._mapping[gdelt_theme]] += 1
            else:
                # Try prefix matching (e.g., "TAX_AI_DEEPLEARNING" matches "TAX_AI")
                for prefix, canonical in self._mapping.items():
                    if gdelt_theme.startswith(prefix):
                        theme_counts[canonical] += 1
                        break

        if not theme_counts:
            return []

        total_articles = len(profile.news_titles) or 1
        max_count = max(theme_counts.values())

        themes = []
        for theme_name, count in theme_counts.most_common():
            frequency = count / max_count
            coverage = min(0.15, count / total_articles)
            confidence = min(0.8, 0.25 + frequency * 0.3 + coverage)

            themes.append(Theme(
                name=theme_name,
                confidence=round(confidence, 3),
                source=ExtractionMethod.NEWS,
                evidence=f"Mentioned in {count} GDELT articles",
            ))

        return themes
