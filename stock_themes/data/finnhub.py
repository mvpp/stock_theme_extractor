"""Finnhub company news provider."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import requests

from stock_themes.config import FAKE_USER_AGENT, PROXY_URL, FINNHUB_API_KEY
from stock_themes.exceptions import ProviderError
from stock_themes.models import CompanyProfile

logger = logging.getLogger(__name__)

FINNHUB_API_URL = "https://finnhub.io/api/v1/company-news"


class FinnhubProvider:
    name = "finnhub"

    def is_available(self) -> bool:
        return bool(FINNHUB_API_KEY)

    def fetch(self, ticker: str, company_name: str | None = None) -> CompanyProfile:
        """Fetch recent company news headlines from Finnhub."""
        today = datetime.utcnow().date()
        from_date = today - timedelta(days=90)

        params = {
            "symbol": ticker.upper(),
            "from": from_date.isoformat(),
            "to": today.isoformat(),
            "token": FINNHUB_API_KEY,
        }
        headers = {"User-Agent": FAKE_USER_AGENT}
        proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

        try:
            resp = requests.get(
                FINNHUB_API_URL, params=params, headers=headers,
                timeout=30, proxies=proxies,
            )
            resp.raise_for_status()
            articles = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"Finnhub API failed for {ticker}: {e}")
        except ValueError:
            return CompanyProfile(
                ticker=ticker.upper(),
                name=company_name or "",
                data_sources=["finnhub"],
            )

        if not isinstance(articles, list):
            articles = []

        titles = []
        for article in articles:
            headline = article.get("headline", "")
            if headline:
                titles.append(headline)

        logger.info(f"{ticker}: Finnhub returned {len(titles)} articles")

        return CompanyProfile(
            ticker=ticker.upper(),
            name=company_name or "",
            news_titles=titles,
            data_sources=["finnhub"],
        )
