"""CPC patent code → technology theme mapper."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from stock_themes.models import CompanyProfile, Theme, ExtractionMethod


class PatentMapper:
    name = "patent_mapper"

    def __init__(self):
        mapping_path = Path(__file__).parent.parent / "taxonomy" / "cpc_mapping.json"
        with open(mapping_path) as f:
            self._mapping: dict[str, list[str]] = json.load(f)

    def extract(self, profile: CompanyProfile) -> list[Theme]:
        if not profile.patent_cpc_codes:
            return []

        # Count how many patents map to each theme
        theme_counts: Counter = Counter()
        for cpc_code in profile.patent_cpc_codes:
            matched_themes = self._lookup(cpc_code)
            for theme in matched_themes:
                theme_counts[theme] += 1

        if not theme_counts:
            return []

        # Convert counts to confidence scores
        max_count = max(theme_counts.values())
        total_patents = profile.patent_count or len(profile.patent_cpc_codes)

        themes = []
        for theme_name, count in theme_counts.most_common():
            # Confidence based on how many patents fall in this theme
            # relative to total patents and max theme count
            relative_frequency = count / max_count
            volume_bonus = min(0.2, total_patents / 500)  # More patents = more confident
            confidence = min(0.85, 0.3 + relative_frequency * 0.35 + volume_bonus)

            themes.append(Theme(
                name=theme_name,
                confidence=round(confidence, 3),
                source=ExtractionMethod.PATENT,
                evidence=f"{count} patents with matching CPC codes (of {total_patents} total)",
            ))

        return themes

    def _lookup(self, cpc_code: str) -> list[str]:
        """Look up themes for a CPC code, trying progressively shorter prefixes."""
        # Try exact match first, then shorter prefixes
        # CPC codes look like: G06N (4 chars), G06F17/30 (longer)
        code = cpc_code.strip()
        for length in [len(code), 4, 3]:
            prefix = code[:length]
            if prefix in self._mapping:
                return self._mapping[prefix]
        return []
