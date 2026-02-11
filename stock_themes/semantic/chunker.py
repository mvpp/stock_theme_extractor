"""Text chunking for semantic pre-filtering."""

from __future__ import annotations

import re

from stock_themes.config import CHUNK_SIZE_WORDS


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS) -> list[str]:
    """Split text into chunks of approximately `chunk_size` words.

    Splits on sentence boundaries when possible to avoid cutting mid-sentence.
    Returns non-empty chunks only.
    """
    if not text or not text.strip():
        return []

    # Clean the text
    text = re.sub(r"\s+", " ", text.strip())

    # Split into sentences (rough heuristic)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks = []
    current_chunk: list[str] = []
    current_word_count = 0

    for sentence in sentences:
        word_count = len(sentence.split())

        if current_word_count + word_count > chunk_size and current_chunk:
            # Emit current chunk
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_word_count = word_count
        else:
            current_chunk.append(sentence)
            current_word_count += word_count

    # Don't forget the last chunk
    if current_chunk:
        chunk_text_str = " ".join(current_chunk)
        if chunk_text_str.strip():
            chunks.append(chunk_text_str)

    return chunks


def collect_all_text(profile) -> str:
    """Collect all text sources from a CompanyProfile into a single string."""
    parts = []

    if profile.business_description:
        parts.append(profile.business_description)
    if profile.business_summary:
        parts.append(profile.business_summary)
    if profile.risk_factors:
        parts.append(profile.risk_factors)
    if profile.patent_titles:
        parts.append(" ".join(profile.patent_titles))
    if profile.news_titles:
        parts.append(" ".join(profile.news_titles))
    if profile.social_text:
        parts.append(profile.social_text)

    return " ".join(parts)
