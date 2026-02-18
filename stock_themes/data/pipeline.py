"""Data pipeline: orchestrates providers and merges results."""

from __future__ import annotations

import logging
import time

from stock_themes.config import SEC_RATE_LIMIT_DELAY, YAHOO_RATE_LIMIT_DELAY
from stock_themes.models import CompanyProfile

logger = logging.getLogger(__name__)


class DataPipeline:
    """Fetches data from all providers and merges into a single CompanyProfile.

    Uses a two-pass approach:
      Pass 1 — core providers (Yahoo Finance, SEC EDGAR) to get the company name.
      Pass 2 — enrichment providers (PatentsView, GDELT, StockTwits) that need
               the company name to query their APIs.
    """

    def __init__(self, providers: list | None = None):
        if providers is not None:
            # Legacy: caller supplied a flat list — treat all as core providers
            self.core_providers = providers
            self.enrichment_providers = []
        else:
            self.core_providers, self.enrichment_providers = self._default_providers()

    def _default_providers(self) -> tuple[list, list]:
        """Return (core_providers, enrichment_providers)."""
        from stock_themes.data.yahoo import YahooFinanceProvider
        from stock_themes.data.sec_edgar import SECEdgarProvider

        core = []
        yahoo = YahooFinanceProvider()
        if yahoo.is_available():
            core.append(yahoo)

        edgar = SECEdgarProvider()
        if edgar.is_available():
            core.append(edgar)

        enrichment = []
        try:
            from stock_themes.data.patents import PatentsViewProvider
            enrichment.append(PatentsViewProvider())
        except ImportError:
            pass

        try:
            from stock_themes.data.news import GDELTProvider
            enrichment.append(GDELTProvider())
        except ImportError:
            pass

        try:
            from stock_themes.data.social import StockTwitsProvider
            enrichment.append(StockTwitsProvider())
        except ImportError:
            pass

        return core, enrichment

    def fetch(self, ticker: str, db_path: str | None = None) -> CompanyProfile:
        """Fetch from all providers and merge.

        Args:
            ticker: Stock ticker symbol.
            db_path: If provided, StockTwits reads accumulated messages from
                     this SQLite DB instead of making a live API call.
        """
        # --- Pass 1: core providers (Yahoo, EDGAR) ---
        core_profiles: list[CompanyProfile] = []
        for provider in self.core_providers:
            if not provider.is_available():
                logger.info(f"Skipping {provider.name}: not available")
                continue
            try:
                profile = provider.fetch(ticker)
                core_profiles.append(profile)
                logger.info(f"Fetched {ticker} from {provider.name}")
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed for {ticker}: {e}")

            if provider.name == "sec_edgar":
                time.sleep(SEC_RATE_LIMIT_DELAY)
            elif provider.name == "yahoo_finance":
                time.sleep(YAHOO_RATE_LIMIT_DELAY)

        if not core_profiles:
            raise RuntimeError(f"All core providers failed for ticker '{ticker}'")

        # Merge core profiles to get company name before enrichment
        base = self._merge(ticker, core_profiles)

        # --- Pass 2: enrichment providers (need company name) ---
        enrichment_profiles: list[CompanyProfile] = []
        for provider in self.enrichment_providers:
            if not provider.is_available():
                continue
            try:
                if provider.name == "stocktwits":
                    if db_path:
                        # Read accumulated monthly messages from DB
                        from stock_themes.data.social import get_monthly_social_text
                        social_text = get_monthly_social_text(db_path, ticker)
                        if social_text:
                            enrichment_profiles.append(CompanyProfile(
                                ticker=ticker.upper(),
                                name=base.name,
                                social_text=social_text,
                                data_sources=["stocktwits"],
                            ))
                    else:
                        # Live fetch of today's 30 messages
                        profile = provider.fetch(ticker)
                        enrichment_profiles.append(profile)
                else:
                    # Patents and news need company name
                    profile = provider.fetch(ticker, company_name=base.name)
                    enrichment_profiles.append(profile)
                logger.info(f"Fetched {ticker} from {provider.name}")
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed for {ticker}: {e}")

        return self._merge(ticker, [base] + enrichment_profiles)

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
