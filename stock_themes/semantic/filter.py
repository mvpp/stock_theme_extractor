"""Cosine similarity pre-filter for theme extraction."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sentence_transformers import util

from stock_themes.config import SIMILARITY_THRESHOLD
from stock_themes.models import CompanyProfile
from stock_themes.semantic.chunker import chunk_text, collect_all_text
from stock_themes.semantic.embedder import get_theme_embeddings, embed_chunks

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Result of semantic pre-filtering."""

    relevant_chunks: list[str] = field(default_factory=list)
    matched_themes: dict[str, float] = field(default_factory=dict)  # theme -> max score
    all_chunks: list[str] = field(default_factory=list)
    total_chunks: int = 0
    relevant_count: int = 0


def semantic_filter(
    profile: CompanyProfile,
    threshold: float = SIMILARITY_THRESHOLD,
) -> FilterResult:
    """Pre-filter text chunks by cosine similarity against theme taxonomy.

    Args:
        profile: Company profile with text data.
        threshold: Minimum cosine similarity to keep a chunk.

    Returns:
        FilterResult with relevant chunks and matched themes.
    """
    text = collect_all_text(profile)
    if not text.strip():
        return FilterResult()

    chunks = chunk_text(text)
    if not chunks:
        return FilterResult()

    # Get theme embeddings (cached)
    theme_names, theme_embeddings = get_theme_embeddings()

    # Embed chunks
    chunk_embeddings = embed_chunks(chunks)
    if chunk_embeddings.numel() == 0:
        return FilterResult(all_chunks=chunks, total_chunks=len(chunks))

    # Compute cosine similarity matrix: [num_chunks × num_themes]
    similarity = util.cos_sim(chunk_embeddings, theme_embeddings)

    relevant_chunks = []
    matched_themes: dict[str, float] = {}

    for i, chunk in enumerate(chunks):
        max_sim = similarity[i].max().item()
        if max_sim >= threshold:
            relevant_chunks.append(chunk)

            # Record which themes this chunk matched
            for j in range(len(theme_names)):
                score = similarity[i][j].item()
                if score >= threshold:
                    theme = theme_names[j]
                    if theme not in matched_themes or score > matched_themes[theme]:
                        matched_themes[theme] = score

    logger.info(
        f"{profile.ticker}: {len(relevant_chunks)}/{len(chunks)} chunks passed "
        f"filter (threshold={threshold}), {len(matched_themes)} themes matched"
    )

    return FilterResult(
        relevant_chunks=relevant_chunks,
        matched_themes=matched_themes,
        all_chunks=chunks,
        total_chunks=len(chunks),
        relevant_count=len(relevant_chunks),
    )
