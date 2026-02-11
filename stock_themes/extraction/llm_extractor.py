"""LLM-based theme extractor using Kimi K2.5 via OpenAI-compatible API."""

from __future__ import annotations

import json
import logging
import os

from stock_themes.config import MOONSHOT_API_KEY, LLM_BASE_URL, LLM_MODEL
from stock_themes.models import CompanyProfile, Theme, ExtractionMethod
from stock_themes.semantic.filter import FilterResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a financial analyst specializing in thematic investing.
Given text about a company, extract the investment themes that apply.

Themes should be:
- Lowercase, 1-3 words each (e.g., "artificial intelligence", "cloud computing", "mobile")
- Specific enough to be actionable (not just "technology")
- Relevant to how thematic ETFs categorize stocks

Return a JSON array of objects with "theme" and "confidence" (0.0-1.0) keys.
Return at most 15 themes. Sort by confidence descending.
Output ONLY valid JSON, no other text.

Example output:
[
  {"theme": "artificial intelligence", "confidence": 0.95},
  {"theme": "cloud computing", "confidence": 0.85},
  {"theme": "wearable technology", "confidence": 0.80}
]"""


class LLMExtractor:
    name = "llm"

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None):
        self.api_key = api_key or MOONSHOT_API_KEY
        self.base_url = base_url or LLM_BASE_URL
        self.model = model or LLM_MODEL

    def is_available(self) -> bool:
        return bool(self.api_key)

    def extract(self, profile: CompanyProfile,
                filter_result: FilterResult | None = None) -> list[Theme]:
        """Extract themes using LLM on pre-filtered relevant chunks.

        If filter_result is provided, uses only the relevant chunks.
        Otherwise sends the business summary/description directly.
        """
        if not self.is_available():
            logger.warning("LLM extractor not available (no API key)")
            return []

        # Build user prompt from pre-filtered chunks or raw text
        user_prompt = self._build_prompt(profile, filter_result)
        if not user_prompt:
            return []

        raw_themes = self._call_llm(user_prompt)
        return [
            Theme(
                name=t["theme"].strip().lower(),
                confidence=min(1.0, max(0.0, t["confidence"])),
                source=ExtractionMethod.LLM,
                evidence="LLM extraction from pre-filtered text",
            )
            for t in raw_themes
            if t.get("theme") and t.get("confidence")
        ]

    def _build_prompt(self, profile: CompanyProfile,
                      filter_result: FilterResult | None) -> str:
        parts = [f"Company: {profile.name} ({profile.ticker})"]

        if profile.sector:
            parts.append(f"Sector: {profile.sector}")
        if profile.industry:
            parts.append(f"Industry: {profile.industry}")

        if filter_result and filter_result.relevant_chunks:
            # Use pre-filtered relevant chunks (much smaller than full text)
            chunks_text = "\n\n".join(filter_result.relevant_chunks[:10])
            parts.append(f"Relevant business text:\n{chunks_text}")
        elif profile.business_description:
            # Fallback: truncate raw description
            parts.append(
                f"Business description:\n{profile.business_description[:4000]}"
            )
        elif profile.business_summary:
            parts.append(f"Business summary:\n{profile.business_summary}")
        else:
            return ""

        return "\n\n".join(parts)

    def _call_llm(self, user_prompt: str) -> list[dict]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=600,
            )
            content = response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return []

        try:
            # Try to parse JSON from the response
            content = content.strip()
            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            parsed = json.loads(content)
            if isinstance(parsed, dict) and "themes" in parsed:
                return parsed["themes"]
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")

        return []
