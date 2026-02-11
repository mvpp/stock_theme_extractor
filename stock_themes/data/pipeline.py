"""Data pipeline: orchestrates providers and merges results."""

from __future__ import annotations

import logging
import time

from stock_themes.config import SEC_RATE_LIMIT_DELAY, YAHOO_RATE_LIMIT_DELAY
from stock_themes.models import CompanyProfile

logger = logging.getLogger(__name__)


class DataPipeline:
    """Fetches data from all providers and merges into a single CompanyProfile."""

    def __init__(self, providers: list | None = None):
        self.providers = providers or self._default_providers()

    def _default_providers(self) -> list:
        from stock_themes.data.yahoo import YahooFinanceProvider
        from stock_themes.data.sec_edgar import SECEdgarProvider

        providers = []

        yahoo = YahooFinanceProvider()
        if yahoo.is_available():
            providers.append(yahoo)

        edgar = SECEdgarProvider()
        if edgar.is_available():
            providers.append(edgar)

        # Enrichment providers (optional)
        try:
            from stock_themes.data.patents import PatentsViewProvider
            providers.append(PatentsViewProvider())
        except ImportError:
            pass

        try:
            from stock_themes.data.news import GDELTProvider
            providers.append(GDELTProvider())
        except ImportError:
            pass

        return providers

    def fetch(self, ticker: str) -> CompanyProfile:
        """Fetch from all available providers and merge."""
        profiles: list[CompanyProfile] = []

        for provider in self.providers:
            if not provider.is_available():
                logger.info(f"Skipping {provider.name}: not available")
                continue
            try:
                profile = provider.fetch(ticker)
                profiles.append(profile)
                logger.info(f"Fetched {ticker} from {provider.name}")
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed for {ticker}: {e}")

            # Respect rate limits
            if provider.name == "sec_edgar":
                time.sleep(SEC_RATE_LIMIT_DELAY)
            elif provider.name == "yahoo_finance":
                time.sleep(YAHOO_RATE_LIMIT_DELAY)

        if not profiles:
            raise RuntimeError(f"All providers failed for ticker '{ticker}'")

        return self._merge(ticker, profiles)

    def _merge(self, ticker: str, profiles: list[CompanyProfile]) -> CompanyProfile:
        """Merge profiles: first non-None value wins for scalar fields,
        lists are concatenated."""
        merged = CompanyProfile(ticker=ticker.upper(), name="")

        scalar_fields = [
            "name", "sector", "industry", "sic_code", "market_cap",
            "exchange", "employees", "website",
            "business_summary", "business_description", "risk_factors",
            "news_tone", "social_text",
        ]
        for field_name in scalar_fields:
            for profile in profiles:
                value = getattr(profile, field_name, None)
                if value and not getattr(merged, field_name, None):
                    setattr(merged, field_name, value)

        # Merge list fields
        for profile in profiles:
            merged.patent_titles.extend(profile.patent_titles)
            merged.patent_cpc_codes.extend(profile.patent_cpc_codes)
            merged.news_themes.extend(profile.news_themes)
            merged.news_titles.extend(profile.news_titles)

        # Sum patent count
        merged.patent_count = sum(p.patent_count for p in profiles)

        # Merge social sentiment (take first non-None)
        for profile in profiles:
            if profile.social_sentiment:
                merged.social_sentiment = profile.social_sentiment
                break

        # Track all sources
        merged.data_sources = []
        for p in profiles:
            merged.data_sources.extend(p.data_sources)

        return merged
