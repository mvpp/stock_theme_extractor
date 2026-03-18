const BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Existing types
// ---------------------------------------------------------------------------

export interface ThemeRanking {
  theme_name: string;
  category: string | null;
  stock_count: number;
  total_market_cap: number;
  avg_confidence: number;
  momentum: number;
  regime: string;
}

export interface StockInfo {
  ticker: string;
  name: string;
  market_cap: number | null;
  confidence: number;
  source: string;
}

export interface ThemeDetail {
  theme_name: string;
  stock_count: number;
  total_market_cap: number;
  avg_confidence: number;
  regime: string;
  regime_color: string;
  stocks: StockInfo[];
}

export interface RegimeInfo {
  theme_name: string;
  regime: string;
  color: string;
  signals: Record<string, number>;
}

export interface DriftInfo {
  theme_name: string;
  drift_score: number;
  period: { from: string; to: string };
  entrants: string[];
  exits: string[];
  weekly_drift: { date: string; jaccard: number }[];
  sub_theme_shift: Record<string, { t0_pct: number; t1_pct: number; t0_count: number; t1_count: number }>;
}

export interface HistoryPoint {
  snapshot_date: string;
  stock_count: number;
  total_market_cap: number | null;
  avg_confidence: number | null;
  news_mention_count: number;
}

export interface SearchResults {
  query: string;
  themes: { name: string; stock_count: number; category: string }[];
  stocks: { ticker: string; name: string; market_cap: number | null; match_reason?: string }[];
}

export interface PromotionCandidate {
  theme_text: string;
  stock_count: number;
  avg_confidence: number;
  avg_distinctiveness: number;
  tickers: string;
  mapped_canonical: string | null;
  avg_mapped_similarity: number;
  avg_quality?: number;
  representative_tickers?: string[];
  recommended_branch?: string | null;
}

export interface TaxonomyNode {
  name: string;
  stock_count: number;
  children: TaxonomyNode[];
}

export interface StockDetail {
  ticker: string;
  name: string;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
  themes: { name: string; confidence: number; source: string; tier: string;
    distinctiveness?: number; freshness?: number; quality_score?: number;
    mapped_canonical?: string | null }[];
  investor_holdings?: InvestorHolding[];
}

// ---------------------------------------------------------------------------
// New types
// ---------------------------------------------------------------------------

export interface DiscoverResult {
  query: string;
  canonical: { name: string; category: string | null; description: string;
    stock_count: number; avg_confidence: number }[];
  open: { theme_text: string; stock_count: number; avg_confidence: number;
    tickers: string[]; mapped_canonical: string | null }[];
  stocks: { ticker: string; name: string; market_cap: number | null }[];
}

export interface EmergingTheme {
  theme_text: string;
  stock_count: number;
  avg_confidence: number;
  avg_distinctiveness: number;
  avg_freshness: number | null;
  avg_quality: number;
  tickers: string;
  mapped_canonical: string | null;
  avg_mapped_similarity: number;
  representative_tickers?: string[];
  recommended_branch?: string | null;
}

export interface NarrativeTheme {
  theme_text: string;
  stock_count: number;
  avg_confidence: number;
  avg_distinctiveness: number;
  avg_freshness: number | null;
  tickers: string;
}

export interface HeatmapCategory {
  name: string;
  total_stocks: number;
  children: { name: string; stock_count: number; avg_confidence: number;
    avg_freshness: number }[];
}

export interface InvestorHolding {
  ticker?: string;
  name?: string;
  investor_name: string;
  investor_short: string;
  change_type: string;
  shares_current: number | null;
  shares_previous: number | null;
  pct_change: number | null;
  filing_date: string | null;
}

export interface TradeabilityScore {
  theme_name: string;
  tradeability_score: number;
  components: {
    relevance: number;
    uniqueness: number;
    recency: number;
    corroboration: number;
    narrative_intensity: number;
    taxonomy_depth: number;
  };
}

export interface OpenVariant {
  theme_text: string;
  stock_count: number;
  avg_confidence: number;
  avg_distinctiveness: number;
  avg_freshness: number | null;
  tickers: string;
}

export interface StockChange {
  entrants: string[];
  exits: string[];
  period_days: number;
}

export interface ScreenerResult {
  ticker: string;
  name: string;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
  themes: { name: string; confidence: number; source: string }[];
}

export interface ScreenerFilters {
  themes?: string[];
  narratives?: string[];
  min_confidence?: number;
  min_distinctiveness?: number;
  min_freshness?: number;
  sources?: string[];
  sectors?: string[];
  min_market_cap?: number;
  has_13f_activity?: boolean;
  near_promotion?: boolean;
  sort_by?: string;
  limit?: number;
}

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

export const api = {
  // Discover (home page search)
  discover: (q: string, sortBy = 'confidence') =>
    get<DiscoverResult>(`/discover?q=${encodeURIComponent(q)}&sort_by=${sortBy}`),

  // Themes
  themes: {
    top: (sortBy = 'stock_count', limit = 10) =>
      get<ThemeRanking[]>(`/themes/top?sort_by=${sortBy}&limit=${limit}`),
    detail: (name: string) =>
      get<ThemeDetail>(`/themes/${encodeURIComponent(name)}`),
    regime: (name: string) =>
      get<RegimeInfo>(`/themes/${encodeURIComponent(name)}/regime`),
    drift: (name: string, days = 90) =>
      get<DriftInfo>(`/themes/${encodeURIComponent(name)}/drift?days=${days}`),
    history: (name: string, days = 90) =>
      get<HistoryPoint[]>(`/themes/${encodeURIComponent(name)}/history?days=${days}`),
    openVariants: (name: string) =>
      get<OpenVariant[]>(`/themes/${encodeURIComponent(name)}/open-variants`),
    stockChanges: (name: string, days = 30) =>
      get<StockChange>(`/themes/${encodeURIComponent(name)}/stock-changes?days=${days}`),
    tradeability: (name: string) =>
      get<TradeabilityScore>(`/themes/${encodeURIComponent(name)}/tradeability`),
    emerging: (limit = 20) =>
      get<EmergingTheme[]>(`/themes/emerging?limit=${limit}`),
  },

  // Stocks
  stocks: {
    detail: (ticker: string) => get<StockDetail>(`/stocks/${ticker}`),
    byTheme: (theme: string) => get<StockInfo[]>(`/stocks?theme=${encodeURIComponent(theme)}`),
  },

  // Search (legacy, redirects to discover)
  search: (q: string) => get<SearchResults>(`/search?q=${encodeURIComponent(q)}`),

  // Promotions
  promotions: {
    candidates: () => get<PromotionCandidate[]>('/promotions/candidates'),
    promote: (body: { open_theme_text: string; canonical_name: string; parent_theme?: string; category?: string }) =>
      post('/promotions/promote', body),
    dismiss: (open_theme_text: string) =>
      post('/promotions/dismiss', { open_theme_text }),
  },

  // Narratives & 13F
  narratives: {
    list: (minConfidence = 0.3) =>
      get<NarrativeTheme[]>(`/narratives?min_confidence=${minConfidence}`),
    trends: (days = 30) =>
      get<NarrativeTheme[]>(`/narratives/trends?days=${days}`),
    heatmap: () =>
      get<HeatmapCategory[]>('/narratives/heatmap'),
    stocks: (text: string) =>
      get<StockInfo[]>(`/narratives/${encodeURIComponent(text)}/stocks`),
  },

  investors: {
    activity: (limit = 50) =>
      get<InvestorHolding[]>(`/investor-activity?limit=${limit}`),
    forStock: (ticker: string) =>
      get<InvestorHolding[]>(`/investor-activity/${ticker}`),
  },

  // Screener
  screener: (filters: ScreenerFilters) =>
    post<ScreenerResult[]>('/screener', filters),

  // Taxonomy
  taxonomy: () => get<TaxonomyNode[]>('/taxonomy/tree'),

  // Admin
  stats: () => get<Record<string, number>>('/stats'),
};
