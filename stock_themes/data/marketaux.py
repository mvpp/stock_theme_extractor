"""MarketAux news API provider."""

from __future__ import annotations

import logging
from datetime import datetime

import requests

from stock_themes.config import (
    FAKE_USER_AGENT, PROXY_URL, MARKETAUX_API_TOKEN,
    MARKETAUX_API_URL, MARKETAUX_LIMIT, MARKETAUX_LANGUAGE,
)
from stock_themes.exceptions import ProviderError
from stock_themes.models import CompanyProfile, DatedArticle

logger = logging.getLogger(__name__)


class MarketAuxProvider:
    name = "marketaux"

    def is_available(self) -> bool:
        return bool(MARKETAUX_API_TOKEN)

    def fetch(self, ticker: str, company_name: str | None = None) -> CompanyProfile:
        """Fetch news article titles from MarketAux for a ticker."""
        params = {
            "api_token": MARKETAUX_API_TOKEN,
            "symbols": ticker.upper(),
            "language": MARKETAUX_LANGUAGE,
            "limit": MARKETAUX_LIMIT,
        }
        headers = {"User-Agent": FAKE_USER_AGENT}
        proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

        try:
            resp = requests.get(
                MARKETAUX_API_URL, params=params, headers=headers,
                timeout=30, proxies=proxies,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"MarketAux API failed for {ticker}: {e}")
        except ValueError:
            return CompanyProfile(
                ticker=ticker.upper(),
                name=company_name or "",
                data_sources=["marketaux"],
            )

        articles = data.get("data", [])
        titles = []
        dated = []
        for article in articles:
            title = article.get("title", "")
            if title:
                titles.append(title)
                # MarketAux returns "published_at" as ISO 8601
                pub_str = article.get("published_at", "")
                pub_dt = None
                if pub_str:
                    try:
                        pub_dt = datetime.fromisoformat(
                            pub_str.replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                    except (ValueError, TypeError):
                        pass
                dated.append(DatedArticle(title=title, published_at=pub_dt))

        logger.info(f"{ticker}: MarketAux returned {len(titles)} articles")

        return CompanyProfile(
            ticker=ticker.upper(),
            name=company_name or "",
            news_titles=titles,
            dated_articles=dated,
            data_sources=["marketaux"],
        )
