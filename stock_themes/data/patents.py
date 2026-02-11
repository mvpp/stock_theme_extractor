"""PatentsView API provider for patent data."""

from __future__ import annotations

import logging

import requests

from stock_themes.exceptions import ProviderError
from stock_themes.models import CompanyProfile

logger = logging.getLogger(__name__)

PATENTSVIEW_API = "https://search.patentsview.org/api/v1/patent/"


class PatentsViewProvider:
    name = "patentsview"

    def is_available(self) -> bool:
        return True

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
            params = {
                "q": {"_contains": {"assignees.assignee_organization": clean_name}},
                "f": [
                    "patent_id",
                    "patent_title",
                    "patent_abstract",
                    "patent_date",
                    "cpcs.cpc_group_id",
                    "cpcs.cpc_subgroup_id",
                ],
                "o": {"per_page": 100},
                "s": [{"patent_date": "desc"}],
            }

            resp = requests.post(PATENTSVIEW_API, json=params, timeout=30)
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

            cpcs = patent.get("cpcs", [])
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
