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
    regime_score: float | None = None
    regime_direction: str = "stable"


class ThemeDetail(BaseModel):
    theme_name: str
    category: str | None = None
    stock_count: int
    total_market_cap: float
    avg_confidence: float
    regime: str
    regime_score: float | None = None
    regime_direction: str = "stable"
    watch_status: str | None = None
    regime_color: str = "#6b7280"
    regime_signals: dict | None = None
    stocks: list[dict] = []


class RegimeResponse(BaseModel):
    theme_name: str
    regime_score: float
    regime_label: str
    regime_direction: str
    watch_status: str | None = None
    color: str
    signals: dict
    raw_score: float | None = None
    clamped_delta: float | None = None


class RegimeHistoryPoint(BaseModel):
    snapshot_date: str
    regime_score: float
    regime_label: str
    regime_direction: str
    watch_status: str | None = None


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
    regime_score: float | None = None


class ThemeTechnicals(BaseModel):
    theme_name: str
    snapshot_date: str | None = None
    avg_ma20_distance_pct: float | None = None
    pct_above_ma20: float | None = None
    avg_volume_trend: float | None = None
    avg_analyst_upside_pct: float | None = None
    avg_positive_surprises: float | None = None
    stocks: list[dict] = []


class StockTechnicals(BaseModel):
    ticker: str
    price_date: str | None = None
    close_price: float | None = None
    ma20: float | None = None
    ma20_distance_pct: float | None = None
    volume_20d_avg: int | None = None
    volume_trend: float | None = None
    analyst_target: float | None = None
    analyst_upside_pct: float | None = None
    analyst_count: int | None = None
    recommendation_mean: float | None = None
    positive_surprises: int | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    profit_margin: float | None = None
    return_on_equity: float | None = None
    return_on_assets: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    free_cashflow: float | None = None
    operating_cashflow: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    peg_ratio: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    earnings_growth: float | None = None
    revenue_growth: float | None = None
    trailing_eps: float | None = None
    forward_eps: float | None = None
    held_pct_institutions: float | None = None
    short_pct_of_float: float | None = None
    short_ratio: float | None = None
    insider_buy_count: int | None = None
    insider_sell_count: int | None = None


class DataFreshness(BaseModel):
    pipeline_name: str
    last_run: str | None = None
    status: str | None = None
    tickers_processed: int | None = None
    tickers_failed: int | None = None
    is_stale: bool = True


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
