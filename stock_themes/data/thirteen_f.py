"""SEC EDGAR 13F-HR filing provider for famous investor holdings.

Fetches quarterly 13F filings, parses the information table (XML),
resolves issuer names to tickers, and computes position changes
(new, sold, added, trimmed) between consecutive quarters.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

import requests
import yaml

from stock_themes.config import (
    CACHE_DIR, FAKE_USER_AGENT, SEC_EDGAR_EMAIL, SEC_RATE_LIMIT_DELAY,
    THIRTEEN_F_CACHE_TTL_DAYS, THIRTEEN_F_MIN_POSITION_VALUE,
    THIRTEEN_F_SIGNIFICANT_PCT, THIRTEEN_F_INVESTORS_FILE,
)
from stock_themes.models import Holding, HoldingChange

logger = logging.getLogger(__name__)

_EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_EDGAR_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}"


class ThirteenFProvider:
    """Fetch and compare 13F-HR filings for famous investors."""

    name = "thirteen_f"

    def __init__(self):
        self._investors = self._load_investors()
        self._name_to_ticker_cache: dict[str, str | None] = {}

    def is_available(self) -> bool:
        return bool(self._investors) and bool(SEC_EDGAR_EMAIL)

    def _load_investors(self) -> list[dict]:
        """Load investor registry from YAML file."""
        investors_path = Path(__file__).parent / THIRTEEN_F_INVESTORS_FILE
        if not investors_path.exists():
            logger.warning(f"Investors file not found: {investors_path}")
            return []
        try:
            with open(investors_path) as f:
                data = yaml.safe_load(f)
            return data.get("investors", [])
        except Exception as e:
            logger.error(f"Failed to load investors file: {e}")
            return []

    def fetch_all_investors(
        self,
        db_path: str | None = None,
    ) -> dict[str, list[HoldingChange]]:
        """Fetch 13F data for all registered investors.

        Returns a dict mapping ticker -> list of HoldingChange objects.
        If db_path is provided, uses it to resolve issuer names to tickers.
        """
        # Check aggregate cache
        cached = self._read_aggregate_cache()
        if cached is not None:
            return cached

        all_changes: dict[str, list[HoldingChange]] = defaultdict(list)

        # Build name-to-ticker mapping from DB if available
        if db_path:
            self._build_name_to_ticker_map(db_path)

        for investor in self._investors:
            cik = investor["cik"]
            name = investor["name"]
            short = investor["short_name"]

            try:
                changes = self._fetch_investor_changes(cik, name, short)
                for change in changes:
                    if change.change_type != "unchanged":
                        all_changes[change.ticker].append(change)
                logger.info(
                    f"13F: {name} — {len(changes)} positions, "
                    f"{sum(1 for c in changes if c.change_type != 'unchanged')} changes"
                )
            except Exception as e:
                logger.warning(f"13F: failed to process {name} (CIK {cik}): {e}")

            time.sleep(SEC_RATE_LIMIT_DELAY)

        result = dict(all_changes)
        self._write_aggregate_cache(result)
        return result

    def _fetch_investor_changes(
        self, cik: str, investor_name: str, investor_short: str,
    ) -> list[HoldingChange]:
        """Fetch current and previous 13F filings, compute changes."""
        filings = self._get_13f_filings(cik)
        if len(filings) < 1:
            return []

        current_holdings = self._parse_13f_filing(cik, filings[0])
        previous_holdings = (
            self._parse_13f_filing(cik, filings[1]) if len(filings) >= 2 else []
        )

        return self._compute_changes(
            current_holdings, previous_holdings,
            investor_name, investor_short,
        )

    def _get_13f_filings(self, cik: str) -> list[dict]:
        """Get the two most recent 13F-HR filing metadata from EDGAR."""
        padded_cik = cik.lstrip("0").zfill(10)
        url = _EDGAR_SUBMISSIONS_URL.format(cik=padded_cik)

        resp = self._edgar_get(url)
        if resp is None:
            return []

        try:
            data = resp.json()
        except ValueError:
            return []

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        dates = recent.get("filingDate", [])

        filings_13f = []
        for i, form in enumerate(forms):
            if form in ("13F-HR", "13F-HR/A") and i < len(accessions):
                filings_13f.append({
                    "accession": accessions[i].replace("-", ""),
                    "accession_formatted": accessions[i],
                    "filing_date": dates[i] if i < len(dates) else None,
                    "cik": cik,
                })
                if len(filings_13f) >= 2:
                    break

        return filings_13f

    def _parse_13f_filing(self, cik: str, filing: dict) -> list[Holding]:
        """Parse the information table XML from a 13F filing."""
        accession = filing["accession"]
        accession_fmt = filing["accession_formatted"]
        clean_cik = cik.lstrip("0")

        # Find the information table file
        index_url = (
            f"https://www.sec.gov/Archives/edgar/data/{clean_cik}/{accession}/"
        )

        resp = self._edgar_get(f"{index_url}index.json")
        if resp is None:
            return []

        try:
            index_data = resp.json()
        except ValueError:
            return []

        # Look for the XML information table file
        xml_file = None
        items = index_data.get("directory", {}).get("item", [])
        for item in items:
            name = item.get("name", "").lower()
            if "infotable" in name and name.endswith(".xml"):
                xml_file = item["name"]
                break

        if not xml_file:
            # Try common naming patterns
            for item in items:
                name = item.get("name", "").lower()
                if name.endswith(".xml") and ("13f" in name or "info" in name):
                    xml_file = item["name"]
                    break

        if not xml_file:
            logger.debug(f"No info table XML found for {accession_fmt}")
            return []

        time.sleep(SEC_RATE_LIMIT_DELAY)
        xml_url = f"{index_url}{xml_file}"
        resp = self._edgar_get(xml_url)
        if resp is None:
            return []

        return self._parse_info_table_xml(resp.text)

    def _parse_info_table_xml(self, xml_text: str) -> list[Holding]:
        """Parse 13F information table XML into Holding objects."""
        # Strip namespace for simpler parsing
        xml_text = re.sub(r'\sxmlns[^"]*"[^"]*"', "", xml_text)

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            logger.warning(f"Failed to parse 13F XML: {e}")
            return []

        holdings: list[Holding] = []

        # Find all infoTable entries (handles different tag casing)
        for entry in root.iter():
            tag = entry.tag.lower()
            if "infotable" not in tag:
                continue

            name_elem = entry.find(".//nameOfIssuer") or entry.find(".//NAMEOFISSUER")
            value_elem = entry.find(".//value") or entry.find(".//VALUE")
            shares_elem = (
                entry.find(".//sshPrnamt")
                or entry.find(".//SSHPRNAMT")
                or entry.find(".//shrsOrPrnAmt/sshPrnamt")
            )
            cusip_elem = entry.find(".//cusip") or entry.find(".//CUSIP")

            if name_elem is None or value_elem is None:
                continue

            issuer_name = (name_elem.text or "").strip()
            try:
                value = float((value_elem.text or "0").strip())
            except ValueError:
                value = 0

            try:
                shares = int((shares_elem.text or "0").strip())
            except (ValueError, AttributeError):
                shares = 0

            if value < THIRTEEN_F_MIN_POSITION_VALUE:
                continue

            # Resolve issuer name to ticker
            ticker = self._resolve_ticker(issuer_name)
            if not ticker:
                continue

            holdings.append(Holding(
                ticker=ticker,
                name=issuer_name,
                shares=shares,
                value=value,
            ))

        return holdings

    def _resolve_ticker(self, issuer_name: str) -> str | None:
        """Resolve an issuer name to a ticker symbol."""
        normalized = issuer_name.upper().strip()

        if normalized in self._name_to_ticker_cache:
            return self._name_to_ticker_cache[normalized]

        # Simple heuristic: strip common suffixes and check cache
        for suffix in [" INC", " CORP", " CO", " LTD", " LLC", " LP",
                       " PLC", " GROUP", " HOLDINGS", " CLASS A",
                       " CLASS B", " CLASS C", " COM", " CL A", " CL B"]:
            stripped = normalized.replace(suffix, "").strip()
            if stripped in self._name_to_ticker_cache:
                result = self._name_to_ticker_cache[stripped]
                self._name_to_ticker_cache[normalized] = result
                return result

        self._name_to_ticker_cache[normalized] = None
        return None

    def _build_name_to_ticker_map(self, db_path: str) -> None:
        """Build a mapping from company name variants to ticker."""
        import sqlite3

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT ticker, name FROM stocks").fetchall()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to read stocks table for name resolution: {e}")
            return

        for row in rows:
            ticker = row["ticker"]
            name = (row["name"] or "").upper().strip()
            if name and ticker:
                self._name_to_ticker_cache[name] = ticker
                # Also add stripped variants
                for suffix in [" INC", " CORP", " CO", " LTD", " LLC",
                               " LP", " PLC", " GROUP", " HOLDINGS",
                               ", INC.", ", CORP.", " INC.", " CORP."]:
                    stripped = name.replace(suffix, "").strip()
                    if stripped and stripped != name:
                        self._name_to_ticker_cache[stripped] = ticker

    def _compute_changes(
        self,
        current: list[Holding],
        previous: list[Holding],
        investor_name: str,
        investor_short: str,
    ) -> list[HoldingChange]:
        """Compare two quarters of holdings to detect changes."""
        prev_by_ticker: dict[str, Holding] = {h.ticker: h for h in previous}
        curr_by_ticker: dict[str, Holding] = {h.ticker: h for h in current}

        changes: list[HoldingChange] = []

        # Current positions
        for ticker, curr in curr_by_ticker.items():
            prev = prev_by_ticker.get(ticker)

            if prev is None:
                changes.append(HoldingChange(
                    ticker=ticker,
                    investor_name=investor_name,
                    investor_short=investor_short,
                    change_type="new_position",
                    shares_current=curr.shares,
                    shares_previous=0,
                    pct_change=100.0,
                ))
            elif curr.shares > prev.shares:
                pct = ((curr.shares - prev.shares) / prev.shares * 100
                       if prev.shares > 0 else 100.0)
                changes.append(HoldingChange(
                    ticker=ticker,
                    investor_name=investor_name,
                    investor_short=investor_short,
                    change_type="added",
                    shares_current=curr.shares,
                    shares_previous=prev.shares,
                    pct_change=round(pct, 1),
                ))
            elif curr.shares < prev.shares:
                pct = ((prev.shares - curr.shares) / prev.shares * 100
                       if prev.shares > 0 else 100.0)
                changes.append(HoldingChange(
                    ticker=ticker,
                    investor_name=investor_name,
                    investor_short=investor_short,
                    change_type="trimmed",
                    shares_current=curr.shares,
                    shares_previous=prev.shares,
                    pct_change=round(pct, 1),
                ))
            else:
                changes.append(HoldingChange(
                    ticker=ticker,
                    investor_name=investor_name,
                    investor_short=investor_short,
                    change_type="unchanged",
                    shares_current=curr.shares,
                    shares_previous=prev.shares,
                    pct_change=0.0,
                ))

        # Sold positions (in previous but not in current)
        for ticker, prev in prev_by_ticker.items():
            if ticker not in curr_by_ticker:
                changes.append(HoldingChange(
                    ticker=ticker,
                    investor_name=investor_name,
                    investor_short=investor_short,
                    change_type="sold_entire",
                    shares_current=0,
                    shares_previous=prev.shares,
                    pct_change=-100.0,
                ))

        return changes

    # ---- HTTP helper ----

    def _edgar_get(self, url: str) -> requests.Response | None:
        """GET with SEC EDGAR required headers."""
        headers = {
            "User-Agent": f"stock_themes {SEC_EDGAR_EMAIL}",
            "Accept-Encoding": "gzip, deflate",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp
            logger.debug(f"EDGAR GET {url} returned {resp.status_code}")
            return None
        except requests.RequestException as e:
            logger.debug(f"EDGAR GET failed for {url}: {e}")
            return None

    # ---- Cache ----

    def _cache_dir(self) -> Path:
        d = CACHE_DIR / "thirteen_f"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _read_aggregate_cache(self) -> dict[str, list[HoldingChange]] | None:
        cache_file = self._cache_dir() / "all_investor_changes.json"
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text())
            cached_at = data.get("_cached_at", 0)
            if time.time() - cached_at > THIRTEEN_F_CACHE_TTL_DAYS * 86400:
                return None

            result: dict[str, list[HoldingChange]] = {}
            for ticker, changes_data in data.get("changes", {}).items():
                result[ticker] = [
                    HoldingChange(**c) for c in changes_data
                ]
            logger.info(
                f"13F: loaded cached data for {len(result)} tickers"
            )
            return result
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.debug(f"13F cache read failed: {e}")
            return None

    def _write_aggregate_cache(
        self, changes: dict[str, list[HoldingChange]],
    ) -> None:
        cache_file = self._cache_dir() / "all_investor_changes.json"
        data = {
            "_cached_at": time.time(),
            "changes": {
                ticker: [
                    {
                        "ticker": c.ticker,
                        "investor_name": c.investor_name,
                        "investor_short": c.investor_short,
                        "change_type": c.change_type,
                        "shares_current": c.shares_current,
                        "shares_previous": c.shares_previous,
                        "pct_change": c.pct_change,
                    }
                    for c in clist
                ]
                for ticker, clist in changes.items()
            },
        }
        try:
            cache_file.write_text(json.dumps(data))
        except OSError:
            pass
