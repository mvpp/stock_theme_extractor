"""Social media keyword extractor — runs keyword patterns on social_text only."""

from __future__ import annotations

from stock_themes.models import CompanyProfile, Theme, ExtractionMethod
from stock_themes.extraction.keyword_extractor import THEME_KEYWORDS

import re


class SocialExtractor:
    """Extract themes from social media text (StockTwits messages).

    Reuses the same regex patterns as KeywordExtractor but operates solely on
    profile.social_text and tags results with ExtractionMethod.SOCIAL so they
    receive the correct ensemble weight (0.4 vs keyword's 0.8).
    """

    name = "social"

    def __init__(self):
        self._patterns = {
            theme: [re.compile(p, re.IGNORECASE) for p in patterns]
            for theme, patterns in THEME_KEYWORDS.items()
        }

    def extract(self, profile: CompanyProfile) -> list[Theme]:
        if not profile.social_text or not profile.social_text.strip():
            return []

        text = profile.social_text
        themes: list[Theme] = []

        for theme_name, patterns in self._patterns.items():
            match_count = 0
            first_match_context = None

            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    match_count += len(matches)
                    if first_match_context is None:
                        m = pattern.search(text)
                        if m:
                            start = max(0, m.start() - 40)
                            end = min(len(text), m.end() + 40)
                            first_match_context = text[start:end].strip()

            if match_count >= 2:  # Require at least 2 hits in social text (noisier)
                text_length = len(text)
                density = match_count / (text_length / 1000)
                confidence = min(0.75, 0.25 + density * 0.07)

                themes.append(Theme(
                    name=theme_name,
                    confidence=round(confidence, 3),
                    source=ExtractionMethod.SOCIAL,
                    evidence=first_match_context,
                ))

        themes.sort(key=lambda t: t.confidence, reverse=True)
        return themes
