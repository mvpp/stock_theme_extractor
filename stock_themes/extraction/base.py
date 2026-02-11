"""Base protocol for theme extractors."""

from __future__ import annotations

from typing import Protocol

from stock_themes.models import CompanyProfile, Theme


class ThemeExtractor(Protocol):
    @property
    def name(self) -> str: ...

    def extract(self, profile: CompanyProfile) -> list[Theme]: ...
