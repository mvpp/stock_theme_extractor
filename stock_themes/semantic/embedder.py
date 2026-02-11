"""Sentence-transformer embedding wrapper with theme embedding cache."""

from __future__ import annotations

import logging
from pathlib import Path

import torch

from stock_themes.config import EMBEDDING_MODEL, CACHE_DIR
from stock_themes.taxonomy.themes import THEME_DESCRIPTIONS

logger = logging.getLogger(__name__)

_model = None
_theme_embeddings = None
_theme_names = None

THEME_CACHE_PATH = CACHE_DIR / "theme_embeddings.pt"


def get_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading sentence transformer model: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def get_theme_embeddings() -> tuple[list[str], torch.Tensor]:
    """Get pre-computed theme embeddings, loading from cache if available."""
    global _theme_embeddings, _theme_names

    if _theme_embeddings is not None and _theme_names is not None:
        return _theme_names, _theme_embeddings

    # Try loading from cache
    if THEME_CACHE_PATH.exists():
        try:
            cache = torch.load(THEME_CACHE_PATH, weights_only=True)
            _theme_names = list(THEME_DESCRIPTIONS.keys())
            _theme_embeddings = cache
            if len(_theme_names) == _theme_embeddings.shape[0]:
                logger.info(
                    f"Loaded {len(_theme_names)} theme embeddings from cache"
                )
                return _theme_names, _theme_embeddings
        except Exception as e:
            logger.warning(f"Theme embedding cache invalid, recomputing: {e}")

    # Compute fresh embeddings
    model = get_model()
    _theme_names = list(THEME_DESCRIPTIONS.keys())
    theme_texts = list(THEME_DESCRIPTIONS.values())

    logger.info(f"Computing embeddings for {len(_theme_names)} themes...")
    _theme_embeddings = model.encode(
        theme_texts, convert_to_tensor=True, show_progress_bar=False
    )

    # Cache to disk
    try:
        THEME_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        torch.save(_theme_embeddings, THEME_CACHE_PATH)
        logger.info(f"Cached theme embeddings to {THEME_CACHE_PATH}")
    except Exception as e:
        logger.warning(f"Failed to cache theme embeddings: {e}")

    return _theme_names, _theme_embeddings


def embed_chunks(chunks: list[str]) -> torch.Tensor:
    """Embed a list of text chunks using the sentence transformer."""
    if not chunks:
        return torch.tensor([])
    model = get_model()
    return model.encode(chunks, convert_to_tensor=True, show_progress_bar=False)
