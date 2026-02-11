"""Base protocol for data providers."""

from __future__ import annotations

from typing import Protocol

from stock_themes.models import CompanyProfile


class DataProvider(Protocol):
    @property
    def name(self) -> str: ...

    def is_available(self) -> bool: ...

    def fetch(self, ticker: str) -> CompanyProfile: ...
