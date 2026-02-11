"""SIC code → theme rule-based mapper."""

from __future__ import annotations

import json
from pathlib import Path

from stock_themes.models import CompanyProfile, Theme, ExtractionMethod


class SICMapper:
    name = "sic_mapper"

    def __init__(self):
        mapping_path = Path(__file__).parent.parent / "taxonomy" / "sic_mapping.json"
        with open(mapping_path) as f:
            self._mapping: dict[str, list[str]] = json.load(f)

    def extract(self, profile: CompanyProfile) -> list[Theme]:
        themes: list[Theme] = []
        seen = set()

        # Direct SIC code lookup
        if profile.sic_code:
            sic = profile.sic_code.strip()

            # Exact 4-digit match
            if sic in self._mapping:
                for theme_name in self._mapping[sic]:
                    if theme_name not in seen:
                        themes.append(Theme(
                            name=theme_name,
                            confidence=0.65,
                            source=ExtractionMethod.SIC_MAPPING,
                            evidence=f"SIC code {sic}",
                        ))
                        seen.add(theme_name)

            # Try 2-digit prefix for broader match
            sic_prefix = sic[:2] + "00"
            if sic_prefix in self._mapping and sic_prefix != sic:
                for theme_name in self._mapping[sic_prefix]:
                    if theme_name not in seen:
                        themes.append(Theme(
                            name=theme_name,
                            confidence=0.4,
                            source=ExtractionMethod.SIC_MAPPING,
                            evidence=f"SIC prefix {sic[:2]}xx",
                        ))
                        seen.add(theme_name)

        # Also use Yahoo sector/industry as themes
        if profile.sector:
            sector_lower = profile.sector.lower()
            if sector_lower not in seen:
                themes.append(Theme(
                    name=sector_lower,
                    confidence=0.5,
                    source=ExtractionMethod.SIC_MAPPING,
                    evidence="Yahoo Finance sector",
                ))
                seen.add(sector_lower)

        if profile.industry:
            industry_lower = profile.industry.lower()
            if industry_lower not in seen:
                themes.append(Theme(
                    name=industry_lower,
                    confidence=0.55,
                    source=ExtractionMethod.SIC_MAPPING,
                    evidence="Yahoo Finance industry",
                ))
                seen.add(industry_lower)

        return themes
