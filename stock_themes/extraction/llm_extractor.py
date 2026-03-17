"""LLM-based theme extractor with embedding post-mapping to canonical taxonomy."""

from __future__ import annotations

import json
import logging

from stock_themes.config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    LLM_MAX_INPUT_CHARS, LLM_SIMILARITY_THRESHOLD,
)
from stock_themes.models import CompanyProfile, Theme, OpenTheme, ExtractionMethod

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a financial analyst specializing in thematic investing.
Given text about a company, extract all investment themes that apply.

Be specific and detailed. For example:
- Instead of "healthcare", say "oncology" or "rare disease" or "cardiovascular"
- Instead of "biotechnology", say "monoclonal antibodies" or "gene therapy" or "mRNA"
- Include clinical stage if mentioned (e.g., "phase 3 clinical trial")
- Include disease areas (e.g., "breast cancer", "Alzheimer's disease")
- Include drug modalities (e.g., "CAR-T cell therapy", "antibody-drug conjugate")

Themes should be:
- Lowercase, 1-5 words each
- Specific enough to be actionable (not just "technology" or "healthcare")
- Relevant to how thematic ETFs categorize stocks

Return a JSON array of objects with "theme" and "confidence" (0.0-1.0) keys.
Return at most 20 themes. Sort by confidence descending.
Output ONLY valid JSON, no other text.

Example output:
[
  {"theme": "artificial intelligence", "confidence": 0.95},
  {"theme": "oncology", "confidence": 0.90},
  {"theme": "phase 3 clinical trial", "confidence": 0.85},
  {"theme": "monoclonal antibodies", "confidence": 0.80}
]"""


class LLMExtractor:
    name = "llm"

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None):
        self.api_key = api_key or LLM_API_KEY
        self.base_url = base_url or LLM_BASE_URL
        self.model = model or LLM_MODEL

    def is_available(self) -> bool:
        return bool(self.api_key)

    def extract(self, profile: CompanyProfile) -> tuple[list[Theme], list[OpenTheme]]:
        """Extract themes using LLM on intact SEC text.

        Returns:
            Tuple of (canonical_themes, open_themes).
            Canonical themes map to the fixed taxonomy.
            Open themes are free-form LLM output that didn't map.
        """
        if not self.is_available():
            logger.warning("LLM extractor not available (no API key)")
            return [], []

        user_prompt = self._build_prompt(profile)
        if not user_prompt:
            return [], []

        raw_themes = self._call_llm(user_prompt)
        if not raw_themes:
            return [], []

        return self._map_to_canonical(raw_themes)

    def _build_prompt(self, profile: CompanyProfile) -> str:
        """Build prompt with intact SEC text (not chunked)."""
        parts = [f"Company: {profile.name} ({profile.ticker})"]

        if profile.sector:
            parts.append(f"Sector: {profile.sector}")
        if profile.industry:
            parts.append(f"Industry: {profile.industry}")

        # Send intact SEC text truncated to max_input_chars
        if profile.business_description:
            text = profile.business_description[:LLM_MAX_INPUT_CHARS]
            if profile.risk_factors:
                remaining = LLM_MAX_INPUT_CHARS - len(text)
                if remaining > 500:
                    text += "\n\nRisk Factors:\n" + profile.risk_factors[:remaining]
            parts.append(f"Business description:\n{text}")
        elif profile.business_summary:
            parts.append(f"Business summary:\n{profile.business_summary}")
        else:
            return ""

        return "\n\n".join(parts)

    def _map_to_canonical(self, raw_themes: list[dict]) -> tuple[list[Theme], list[OpenTheme]]:
        """Map free-form LLM themes to canonical taxonomy.

        Two-pass strategy:
          1. Normalizer alias lookup (exact match — fast, high precision)
          2. Embedding cosine similarity fallback (fuzzy match for novel phrases)

        Themes that don't map to canonical are returned as OpenTheme instead of
        being dropped.
        """
        from stock_themes.taxonomy.normalizer import ThemeNormalizer

        normalizer = ThemeNormalizer()
        canonical_themes: list[Theme] = []
        open_themes: list[OpenTheme] = []
        seen_canonical: set[str] = set()
        unmapped: list[tuple[int, dict]] = []

        # Pass 1: normalizer lookup
        for i, raw in enumerate(raw_themes):
            name = raw.get("theme", "").strip().lower()
            if not name:
                continue
            normalized = normalizer.normalize(name)
            if normalizer.is_known(normalized) and normalized not in seen_canonical:
                seen_canonical.add(normalized)
                canonical_themes.append(Theme(
                    name=normalized,
                    confidence=min(1.0, max(0.0, raw.get("confidence", 0.5))),
                    source=ExtractionMethod.LLM,
                    evidence=f"LLM: \"{raw['theme']}\"",
                ))
            else:
                unmapped.append((i, raw))

        # Pass 2: embedding similarity for unmapped themes
        if unmapped:
            from sentence_transformers import util
            from stock_themes.semantic.embedder import get_theme_embeddings, embed_chunks

            theme_names, theme_embeddings = get_theme_embeddings()
            unmapped_texts = [raw["theme"] for _, raw in unmapped]
            llm_embeddings = embed_chunks(unmapped_texts)

            if llm_embeddings.numel() > 0:
                similarity = util.cos_sim(llm_embeddings, theme_embeddings)
                for j, (_, raw) in enumerate(unmapped):
                    max_sim_idx = similarity[j].argmax().item()
                    max_sim = similarity[j][max_sim_idx].item()
                    canonical_name = theme_names[max_sim_idx]
                    conf = min(1.0, max(0.0, raw.get("confidence", 0.5)))

                    if max_sim >= LLM_SIMILARITY_THRESHOLD and canonical_name not in seen_canonical:
                        # Maps to canonical taxonomy
                        seen_canonical.add(canonical_name)
                        canonical_themes.append(Theme(
                            name=canonical_name,
                            confidence=conf,
                            source=ExtractionMethod.LLM,
                            evidence=(
                                f"LLM: \"{raw['theme']}\" -> {canonical_name} "
                                f"(sim={max_sim:.2f})"
                            ),
                        ))
                    else:
                        # Doesn't map — store as open theme
                        open_themes.append(OpenTheme(
                            text=raw["theme"].strip().lower(),
                            confidence=conf,
                            source="llm",
                            evidence=f"LLM raw theme",
                            mapped_canonical=canonical_name,
                            mapped_similarity=round(max_sim, 3),
                        ))

        n_normalizer = len(raw_themes) - len(unmapped)
        n_embedding = len(canonical_themes) - n_normalizer
        logger.info(
            f"LLM: {len(raw_themes)} raw -> {len(canonical_themes)} canonical, "
            f"{len(open_themes)} open "
            f"({n_normalizer} normalizer, {n_embedding} embedding@{LLM_SIMILARITY_THRESHOLD})"
        )
        return canonical_themes, open_themes

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
                temperature=0.6,
                max_tokens=800,
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return []

        if not content or not content.strip():
            logger.warning("LLM returned empty content")
            return []

        try:
            content = content.strip()
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
            logger.warning(f"Failed to parse LLM response: {e}\nRaw content: {content[:500]}")

        return []
