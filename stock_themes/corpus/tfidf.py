"""TF-IDF corpus distinctiveness scoring for stock themes."""

from __future__ import annotations

import logging
import pickle
import sqlite3
from pathlib import Path

import numpy as np

from stock_themes.config import (
    CACHE_DIR,
    CORPUS_NGRAM_RANGE, CORPUS_MAX_FEATURES,
    CORPUS_MIN_DF, CORPUS_MAX_DF,
)

logger = logging.getLogger(__name__)

_CACHE_VECTORIZER = CACHE_DIR / "tfidf_vectorizer.pkl"
_CACHE_MATRIX = CACHE_DIR / "tfidf_matrix.npz"
_CACHE_TICKERS = CACHE_DIR / "tfidf_tickers.pkl"


class CorpusScorer:
    """TF-IDF distinctiveness scoring across the SEC filing corpus.

    Measures how distinctive a theme's terms are for a specific company
    relative to all other companies in the corpus. High score means the
    company talks about this topic much more than average.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.vectorizer = None
        self.tfidf_matrix = None
        self.ticker_index: dict[str, int] = {}  # ticker -> row index

    def build(self) -> int:
        """Rebuild TF-IDF matrix from all filings in DB.

        Returns number of documents indexed.
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from scipy import sparse

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT s.ticker, s.name,
                      COALESCE(
                          (SELECT GROUP_CONCAT(t.name, ' ')
                           FROM stock_themes st JOIN themes t ON t.id = st.theme_id
                           WHERE st.ticker = s.ticker), ''
                      ) as theme_text
               FROM stocks s"""
        ).fetchall()
        conn.close()

        if not rows:
            logger.warning("No stocks in DB for corpus building")
            return 0

        # Build documents: combine company name + any existing theme names
        # We also want to pull business descriptions if stored, but they're
        # not in the DB schema. For now, use what's available.
        tickers = []
        documents = []
        for row in rows:
            ticker = row["ticker"]
            # Use theme text as proxy for company content
            doc = f"{row['name']} {row['theme_text']}".strip()
            if doc:
                tickers.append(ticker)
                documents.append(doc)

        if len(documents) < 3:
            logger.warning(f"Too few documents ({len(documents)}) for meaningful TF-IDF")
            return 0

        self.vectorizer = TfidfVectorizer(
            ngram_range=tuple(CORPUS_NGRAM_RANGE),
            max_features=CORPUS_MAX_FEATURES,
            stop_words="english",
            min_df=CORPUS_MIN_DF,
            max_df=CORPUS_MAX_DF,
            sublinear_tf=True,
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(documents)
        self.ticker_index = {t: i for i, t in enumerate(tickers)}

        # Cache to disk
        with open(_CACHE_VECTORIZER, "wb") as f:
            pickle.dump(self.vectorizer, f)
        sparse.save_npz(_CACHE_MATRIX, self.tfidf_matrix)
        with open(_CACHE_TICKERS, "wb") as f:
            pickle.dump(self.ticker_index, f)

        logger.info(f"TF-IDF corpus built: {len(documents)} docs, "
                     f"{len(self.vectorizer.vocabulary_)} features")
        return len(documents)

    def load(self) -> bool:
        """Load cached vectorizer + matrix. Returns False if not built yet."""
        from scipy import sparse

        if not (_CACHE_VECTORIZER.exists() and _CACHE_MATRIX.exists()
                and _CACHE_TICKERS.exists()):
            return False

        try:
            with open(_CACHE_VECTORIZER, "rb") as f:
                self.vectorizer = pickle.load(f)
            self.tfidf_matrix = sparse.load_npz(_CACHE_MATRIX)
            with open(_CACHE_TICKERS, "rb") as f:
                self.ticker_index = pickle.load(f)
            logger.debug(f"TF-IDF corpus loaded: {self.tfidf_matrix.shape[0]} docs")
            return True
        except Exception as e:
            logger.warning(f"Failed to load TF-IDF cache: {e}")
            return False

    def is_ready(self) -> bool:
        return self.vectorizer is not None and self.tfidf_matrix is not None

    def score_themes(self, ticker: str, theme_texts: list[str]) -> list[float]:
        """Score how distinctive each theme is for this ticker vs. corpus.

        Returns a list of distinctiveness scores (0-1) parallel to theme_texts.
        Score of 0 means the theme's terms are not found or are common boilerplate.
        Score of 1 means maximum distinctiveness.
        """
        if not self.is_ready():
            if not self.load():
                return [0.0] * len(theme_texts)

        row_idx = self.ticker_index.get(ticker.upper())
        if row_idx is None:
            # Ticker not in corpus — score against vocabulary IDF only
            return self._score_by_idf(theme_texts)

        doc_vector = self.tfidf_matrix[row_idx]
        feature_names = self.vectorizer.get_feature_names_out()
        vocab = self.vectorizer.vocabulary_

        scores = []
        for text in theme_texts:
            # Tokenize the theme text using the same analyzer
            try:
                tokens = self.vectorizer.build_analyzer()(text.lower())
            except Exception:
                scores.append(0.0)
                continue

            if not tokens:
                scores.append(0.0)
                continue

            # Look up TF-IDF scores for matching tokens/n-grams
            token_scores = []
            for token in tokens:
                if token in vocab:
                    idx = vocab[token]
                    score = doc_vector[0, idx]
                    if score > 0:
                        token_scores.append(score)

            if token_scores:
                # Average TF-IDF score, normalized to 0-1 range
                raw = float(np.mean(token_scores))
                # TF-IDF values typically range 0-1, cap at 1
                scores.append(min(1.0, raw))
            else:
                scores.append(0.0)

        return scores

    def _score_by_idf(self, theme_texts: list[str]) -> list[float]:
        """Score themes by IDF only (for tickers not in corpus)."""
        if not self.is_ready():
            return [0.0] * len(theme_texts)

        idf = self.vectorizer.idf_
        vocab = self.vectorizer.vocabulary_
        max_idf = float(np.max(idf)) if len(idf) > 0 else 1.0

        scores = []
        for text in theme_texts:
            try:
                tokens = self.vectorizer.build_analyzer()(text.lower())
            except Exception:
                scores.append(0.0)
                continue

            token_scores = []
            for token in tokens:
                if token in vocab:
                    token_scores.append(idf[vocab[token]] / max_idf)

            scores.append(float(np.mean(token_scores)) if token_scores else 0.0)

        return scores
