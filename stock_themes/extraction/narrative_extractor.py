"""Extract market narrative themes from news headlines using LLM."""

from __future__ import annotations

import json
import logging

from stock_themes.config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    NARRATIVE_MAX_TITLES, NARRATIVE_MAX_THEMES,
)
from stock_themes.models import CompanyProfile, OpenTheme

logger = logging.getLogger(__name__)

NARRATIVE_PROMPT = """You are a financial analyst. Given recent news headlines about {company} ({ticker}), extract the market narrative themes — how the market/investors perceive this stock.

Look for:
- Market groupings: "magnificent 7", "FAANG", "meme stock", "penny stock"
- Momentum narratives: "AI winner", "AI loser", "growth story", "turnaround play"
- Macro sensitivity: "rate sensitive", "cyclical", "defensive", "inflation hedge"
- Geopolitical: "China exposure", "tariff risk", "sanctions risk", "war risk"
- Style factors: "value trap", "momentum", "dividend aristocrat", "speculative"
- Event-driven: "M&A target", "activist investor", "short squeeze", "insider buying"
- Sector narratives: "EV bubble", "AI infrastructure", "weight loss drug", "nuclear renaissance"

Rules:
- Only include themes clearly supported by the headlines
- Themes should be lowercase, 1-5 words
- Return at most {max_themes} themes
- Return a JSON array of {{"theme": "...", "confidence": 0.0-1.0}}
- Output ONLY valid JSON, no other text

Headlines:
{headlines}"""


class NarrativeExtractor:
    """Extract market narrative themes from news titles."""

    name = "narrative"

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None):
        self.api_key = api_key or LLM_API_KEY
        self.base_url = base_url or LLM_BASE_URL
        self.model = model or LLM_MODEL

    def is_available(self) -> bool:
        return bool(self.api_key)

    def extract(self, profile: CompanyProfile) -> list[OpenTheme]:
        """Extract narrative themes from news titles using LLM."""
        if not self.is_available():
            logger.debug("Narrative extractor not available (no API key)")
            return []

        if not profile.news_titles:
            logger.debug(f"{profile.ticker}: no news titles for narrative extraction")
            return []

        titles = profile.news_titles[:NARRATIVE_MAX_TITLES]
        headlines = "\n".join(f"- {t}" for t in titles)

        prompt = NARRATIVE_PROMPT.format(
            company=profile.name,
            ticker=profile.ticker,
            max_themes=NARRATIVE_MAX_THEMES,
            headlines=headlines,
        )

        raw_themes = self._call_llm(prompt)

        open_themes = []
        for raw in raw_themes:
            text = raw.get("theme", "").strip().lower()
            if not text:
                continue
            open_themes.append(OpenTheme(
                text=text,
                confidence=min(1.0, max(0.0, raw.get("confidence", 0.5))),
                source="narrative",
                evidence=f"Narrative: from {len(titles)} headlines",
            ))

        logger.info(f"{profile.ticker}: narrative extracted {len(open_themes)} themes "
                     f"from {len(titles)} headlines")
        return open_themes

    def _call_llm(self, prompt: str) -> list[dict]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=400,
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = response.choices[0].message.content
        except Exception as e:
            logger.error(f"Narrative LLM call failed: {e}")
            return []

        if not content or not content.strip():
            return []

        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "themes" in parsed:
                return parsed["themes"]
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Failed to parse narrative LLM response: {e}")

        return []
