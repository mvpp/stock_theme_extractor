"""GDELT DOC 2.0 API provider for news themes."""

from __future__ import annotations

import logging

import requests

from stock_themes.exceptions import ProviderError
from stock_themes.models import CompanyProfile

logger = logging.getLogger(__name__)

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


class GDELTProvider:
    name = "gdelt"

    def is_available(self) -> bool:
        return True

    def fetch(self, ticker: str, company_name: str | None = None) -> CompanyProfile:
        if not company_name:
            return CompanyProfile(
                ticker=ticker.upper(), name="", data_sources=["gdelt"]
            )
        return self.fetch_with_name(ticker, company_name)

    def fetch_with_name(self, ticker: str, company_name: str) -> CompanyProfile:
        """Fetch news themes and tone from GDELT for a company."""
        # Use quoted company name for exact match
        clean_name = company_name.split(",")[0].strip()  # Remove ", Inc." etc.

        try:
            params = {
                "query": f'"{clean_name}" sourcelang:eng',
                "mode": "artlist",
                "maxrecords": "75",
                "timespan": "3months",
                "format": "json",
                "sort": "datedesc",
            }
            resp = requests.get(GDELT_DOC_API, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"GDELT API failed for {company_name}: {e}")
        except ValueError:
            # GDELT sometimes returns non-JSON for empty results
            return CompanyProfile(
                ticker=ticker.upper(), name=company_name,
                data_sources=["gdelt"],
            )

        articles = data.get("articles", [])

        titles = []
        themes = []
        tones = []

        for article in articles:
            title = article.get("title", "")
            if title:
                titles.append(title)

            # GDELT encodes themes in the segtitle field or theme field
            article_themes = article.get("themes", [])
            if isinstance(article_themes, list):
                themes.extend(article_themes)
            elif isinstance(article_themes, str):
                themes.extend(article_themes.split(";"))

            tone = article.get("tone", None)
            if tone is not None:
                try:
                    tones.append(float(tone))
                except (ValueError, TypeError):
                    pass

        # Deduplicate themes
        themes = list(set(themes))
        avg_tone = sum(tones) / len(tones) if tones else None

        logger.info(
            f"{ticker}: GDELT returned {len(articles)} articles, "
            f"{len(themes)} unique themes"
        )

        return CompanyProfile(
            ticker=ticker.upper(),
            name=company_name,
            news_titles=titles,
            news_themes=themes,
            news_tone=avg_tone,
            data_sources=["gdelt"],
        )
