"""PatentsView API provider for patent data."""

from __future__ import annotations

import json
import logging

import requests

from stock_themes.config import PATENTSVIEW_API_KEY, FAKE_USER_AGENT
from stock_themes.exceptions import ProviderError
from stock_themes.models import CompanyProfile

logger = logging.getLogger(__name__)

PATENTSVIEW_API = "https://search.patentsview.org/api/v1/patent/"


class PatentsViewProvider:
    name = "patentsview"

    def is_available(self) -> bool:
        return bool(PATENTSVIEW_API_KEY)

    def fetch(self, ticker: str, company_name: str | None = None) -> CompanyProfile:
        """Search patents by company name (assignee).

        Note: PatentsView searches by assignee name, not ticker.
        The caller should provide the company name from a prior provider.
        """
        if not company_name:
            # We need the company name; caller should have it from Yahoo/EDGAR
            return CompanyProfile(
                ticker=ticker.upper(), name="", data_sources=["patentsview"]
            )

        return self._search_patents(ticker, company_name)

    def fetch_with_name(self, ticker: str, company_name: str) -> CompanyProfile:
        """Fetch patent data for a company by name."""
        return self._search_patents(ticker, company_name)

    def _search_patents(self, ticker: str, company_name: str) -> CompanyProfile:
        """Query PatentsView for patents assigned to this company."""
        # Clean company name for search (remove Inc., Corp., etc.)
        clean_name = self._clean_company_name(company_name)

        try:
            # PatentsView API expects q/f/o/s as JSON-encoded query params
            query_params = {
                "q": json.dumps(
                    {"_contains": {"assignees.assignee_organization": clean_name}}
                ),
                "f": json.dumps([
                    "patent_id",
                    "patent_title",
                    "patent_abstract",
                    "patent_date",
                    "cpc_at_issue.cpc_group_id",
                    "cpc_at_issue.cpc_subclass_id",
                ]),
                "o": json.dumps({"size": 100}),
                "s": json.dumps([{"patent_date": "desc"}]),
            }

            headers = {
                "X-Api-Key": PATENTSVIEW_API_KEY,
                "User-Agent": FAKE_USER_AGENT,
            }
            resp = requests.get(
                PATENTSVIEW_API,
                params=query_params,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ProviderError(f"PatentsView API failed for {company_name}: {e}")

        patents = data.get("patents", [])

        titles = []
        cpc_codes = []
        for patent in patents:
            title = patent.get("patent_title", "")
            if title:
                titles.append(title)

            cpcs = patent.get("cpc_at_issue", [])
            if isinstance(cpcs, list):
                for cpc in cpcs:
                    group_id = cpc.get("cpc_group_id", "")
                    if group_id:
                        cpc_codes.append(group_id)

        # Deduplicate CPC codes
        cpc_codes = list(set(cpc_codes))

        logger.info(
            f"{ticker}: found {len(patents)} patents, "
            f"{len(titles)} titles, {len(cpc_codes)} unique CPC codes"
        )

        return CompanyProfile(
            ticker=ticker.upper(),
            name=company_name,
            patent_titles=titles,
            patent_cpc_codes=cpc_codes,
            patent_count=len(patents),
            data_sources=["patentsview"],
        )

    def _clean_company_name(self, name: str) -> str:
        """Remove common suffixes for better patent search matching."""
        suffixes = [
            " Inc.", " Inc", " Corp.", " Corp", " Corporation",
            " Ltd.", " Ltd", " Limited", " LLC", " L.L.C.",
            " PLC", " plc", " N.V.", " S.A.", " AG", " SE",
            " Co.", " Co", " Company", " Group",
            ",", ".",
        ]
        cleaned = name.strip()
        for suffix in suffixes:
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
        return cleaned
