"""Pydantic response models for the dashboard API."""

from __future__ import annotations

from pydantic import BaseModel


class ThemeRanking(BaseModel):
    theme_name: str
    category: str | None = None
    stock_count: int
    total_market_cap: float
    avg_confidence: float
    momentum: float
    regime: str


class ThemeDetail(BaseModel):
    theme_name: str
    category: str | None = None
    stock_count: int
    total_market_cap: float
    avg_confidence: float
    regime: str
    regime_signals: dict | None = None
    stocks: list[dict] = []


class RegimeResponse(BaseModel):
    theme_name: str
    regime: str
    color: str
    signals: dict


class DriftResponse(BaseModel):
    theme_name: str
    drift_score: float
    period: dict
    entrants: list[str]
    exits: list[str]
    weekly_drift: list[dict]
    sub_theme_shift: dict


class HistoryPoint(BaseModel):
    snapshot_date: str
    stock_count: int
    total_market_cap: float | None
    avg_confidence: float | None
    news_mention_count: int


class StockDetail(BaseModel):
    ticker: str
    name: str
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    themes: list[dict] = []


class SearchResult(BaseModel):
    themes: list[dict] = []
    stocks: list[dict] = []


class PromotionCandidate(BaseModel):
    theme_text: str
    stock_count: int
    avg_confidence: float
    avg_distinctiveness: float
    tickers: str
    mapped_canonical: str | None = None
    avg_quality: float


class PromoteRequest(BaseModel):
    open_theme_text: str
    canonical_name: str
    parent_theme: str | None = None
    category: str | None = None


class DismissRequest(BaseModel):
    open_theme_text: str


class StatsResponse(BaseModel):
    stocks: int
    themes: int
    associations: int
    social_messages: int
    snapshots: int
