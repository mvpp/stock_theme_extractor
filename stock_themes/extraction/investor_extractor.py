"""Extract narrative themes from famous investor 13F holding changes."""

from __future__ import annotations

import logging

from stock_themes.config import THIRTEEN_F_SIGNIFICANT_PCT
from stock_themes.models import CompanyProfile, OpenTheme, HoldingChange

logger = logging.getLogger(__name__)


class InvestorHoldingExtractor:
    """Convert 13F holding changes into open themes."""

    name = "investor"

    def __init__(self, holding_changes: dict[str, list[HoldingChange]]):
        self._changes = holding_changes

    def extract(self, profile: CompanyProfile) -> list[OpenTheme]:
        """Generate open themes from investor holding changes for this ticker."""
        changes = self._changes.get(profile.ticker, [])
        if not changes:
            return []

        themes: list[OpenTheme] = []
        for change in changes:
            theme_text, confidence = self._change_to_theme(change)
            if not theme_text:
                continue

            themes.append(OpenTheme(
                text=theme_text,
                confidence=confidence,
                source="13f",
                evidence=(
                    f"13F: {change.investor_name} {change.change_type} "
                    f"({change.shares_previous:,} -> {change.shares_current:,} shares, "
                    f"{change.pct_change:+.1f}%)"
                ),
            ))

        if themes:
            logger.info(
                f"{profile.ticker}: investor extractor produced "
                f"{len(themes)} themes from 13F data"
            )

        return themes

    def _change_to_theme(self, change: HoldingChange) -> tuple[str, float]:
        """Convert a HoldingChange to (theme_text, confidence)."""
        short = change.investor_short.lower()
        sig_pct = THIRTEEN_F_SIGNIFICANT_PCT

        if change.change_type == "new_position":
            return f"{short} new position", 0.8

        if change.change_type == "sold_entire":
            return f"{short} sold entire position", 0.8

        if change.change_type == "added":
            if change.pct_change > sig_pct:
                return f"{short} significantly added", 0.7
            return f"{short} added", 0.5

        if change.change_type == "trimmed":
            if change.pct_change > sig_pct:
                return f"{short} significantly trimmed", 0.7
            return f"{short} trimmed", 0.5

        return "", 0.0
