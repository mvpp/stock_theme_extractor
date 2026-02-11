"""SEC EDGAR data provider with 10-Q → 10-K → S-1 fallback."""

from __future__ import annotations

import logging

from stock_themes.exceptions import ProviderError
from stock_themes.models import CompanyProfile

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 15_000  # Truncate very long filings


class SECEdgarProvider:
    name = "sec_edgar"

    def __init__(self, identity_email: str | None = None):
        from stock_themes.config import SEC_EDGAR_EMAIL
        self._email = identity_email or SEC_EDGAR_EMAIL

    def is_available(self) -> bool:
        try:
            import edgar  # noqa: F401
            return True
        except ImportError:
            return False

    def fetch(self, ticker: str) -> CompanyProfile:
        """Fetch company data from SEC EDGAR with fallback chain."""
        from edgar import Company, set_identity
        set_identity(self._email)

        try:
            company = Company(ticker.upper())
        except Exception as e:
            raise ProviderError(f"SEC EDGAR company lookup failed for {ticker}: {e}")

        sic_code = None
        try:
            sic_code = str(company.sic) if hasattr(company, "sic") and company.sic else None
        except Exception:
            pass

        company_name = ""
        try:
            company_name = company.name or ""
        except Exception:
            pass

        # Fallback chain: 10-Q → 10-K → S-1
        business_desc = None
        risk_factors = None
        filing_type = None

        for form_type in ["10-Q", "10-K", "S-1"]:
            try:
                desc, risks = self._extract_from_filing(company, form_type)
                if desc:
                    business_desc = desc
                    risk_factors = risks
                    filing_type = form_type
                    logger.info(f"{ticker}: extracted text from {form_type}")
                    break
            except Exception as e:
                logger.debug(f"{ticker}: {form_type} extraction failed: {e}")
                continue

        if not business_desc:
            logger.warning(f"{ticker}: no filing text extracted from any form type")

        return CompanyProfile(
            ticker=ticker.upper(),
            name=company_name,
            sic_code=sic_code,
            business_description=business_desc,
            risk_factors=risk_factors,
            data_sources=["sec_edgar"],
        )

    def _extract_from_filing(
        self, company, form_type: str
    ) -> tuple[str | None, str | None]:
        """Extract business description and risk factors from a filing type."""
        filings = company.get_filings(form=form_type)
        if not filings or len(filings) == 0:
            return None, None

        latest = filings[0]
        filing_obj = latest.obj()

        business_desc = None
        risk_factors = None

        if form_type == "10-K":
            business_desc = self._get_section(filing_obj, [
                "item_1", "item1", "business",
            ])
            risk_factors = self._get_section(filing_obj, [
                "item_1a", "item1a", "risk_factors",
            ])
        elif form_type == "10-Q":
            # 10-Q has MD&A in Item 2, which is the richest text
            business_desc = self._get_section(filing_obj, [
                "item_2", "item2", "management_discussion",
                "mda", "item_1", "item1",
            ])
            risk_factors = self._get_section(filing_obj, [
                "item_1a", "item1a", "risk_factors",
            ])
        elif form_type == "S-1":
            business_desc = self._get_section(filing_obj, [
                "business", "item_1", "summary", "prospectus_summary",
            ])
            risk_factors = self._get_section(filing_obj, [
                "risk_factors", "item_1a",
            ])

        # Truncate if too long
        if business_desc and len(business_desc) > MAX_TEXT_LENGTH:
            business_desc = business_desc[:MAX_TEXT_LENGTH]
        if risk_factors and len(risk_factors) > MAX_TEXT_LENGTH:
            risk_factors = risk_factors[:MAX_TEXT_LENGTH]

        return business_desc, risk_factors

    def _get_section(self, filing_obj, attr_names: list[str]) -> str | None:
        """Try multiple attribute names to find a section."""
        for attr_name in attr_names:
            try:
                value = getattr(filing_obj, attr_name, None)
                if value and isinstance(value, str) and len(value.strip()) > 100:
                    return value.strip()
            except Exception:
                continue
        return None
