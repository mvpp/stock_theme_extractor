import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { ThemeRanking, EmergingTheme, DiscoverResult } from '../api/client'
import RegimeBadge from '../components/RegimeBadge'

function fmt(n: number | null | undefined): string {
  if (n == null) return '-'
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(1)}T`
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(0)}M`
  return `$${n.toFixed(0)}`
}

type SortBy = 'confidence' | 'freshness' | 'distinctiveness' | 'market_cap'

export default function DiscoverPage() {
  const [params, setParams] = useSearchParams()
  const queryFromUrl = params.get('q') || ''
  const [query, setQuery] = useState(queryFromUrl)
  const [sortBy, setSortBy] = useState<SortBy>('confidence')

  // Leaderboard data
  const [topThemes, setTopThemes] = useState<ThemeRanking[]>([])
  const [emerging, setEmerging] = useState<EmergingTheme[]>([])
  const [loadingBoards, setLoadingBoards] = useState(true)

  // Search results
  const [results, setResults] = useState<DiscoverResult | null>(null)
  const [searching, setSearching] = useState(false)

  // Load leaderboards on mount
  useEffect(() => {
    Promise.all([
      api.themes.top('stock_count', 10),
      api.themes.emerging(10),
    ]).then(([top, emg]) => {
      setTopThemes(top)
      setEmerging(emg)
    }).finally(() => setLoadingBoards(false))
  }, [])

  // Perform search when URL query changes
  useEffect(() => {
    if (queryFromUrl) {
      setQuery(queryFromUrl)
      setSearching(true)
      api.discover(queryFromUrl, sortBy)
        .then(setResults)
        .finally(() => setSearching(false))
    } else {
      setResults(null)
    }
  }, [queryFromUrl, sortBy])

  const onSearch = (e: FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      setParams({ q: query.trim() })
    }
  }

  return (
    <div>
      {/* Hero Search */}
      <div className="mb-8">
        <form onSubmit={onSearch} className="max-w-2xl mx-auto">
          <div className="relative">
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search themes, narratives, or stocks... (e.g. 'weightloss drug', 'AI', 'NVDA')"
              className="w-full px-5 py-3 text-lg bg-card border border-border rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent"
            />
            <button type="submit" className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-accent">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>
          </div>
        </form>
      </div>

      {/* Search Results */}
      {queryFromUrl && (
        <div className="mb-8">
          {/* Sort bar */}
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-text-primary">
              Results for &ldquo;{queryFromUrl}&rdquo;
            </h2>
            <div className="flex gap-1 bg-[#111] rounded-lg p-0.5">
              {(['confidence', 'freshness', 'distinctiveness', 'market_cap'] as SortBy[]).map(s => (
                <button
                  key={s}
                  onClick={() => setSortBy(s)}
                  className={`px-2 py-1 text-xs font-medium rounded-md transition-colors ${
                    sortBy === s ? 'bg-card-hover text-text-primary' : 'text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {s.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          {searching ? (
            <div className="text-center py-8 text-text-muted">Searching...</div>
          ) : results && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Canonical themes */}
              <div className="bg-card rounded-lg border border-border p-4">
                <h3 className="text-sm font-semibold text-text-muted uppercase mb-3">Canonical Themes</h3>
                {results.canonical.length === 0 && <p className="text-text-muted text-sm">No matches</p>}
                <div className="space-y-2">
                  {results.canonical.map(t => (
                    <Link key={t.name} to={`/themes/${encodeURIComponent(t.name)}`}
                      className="block p-2 rounded hover:bg-card-hover transition-colors">
                      <div className="text-sm font-medium text-accent">{t.name}</div>
                      <div className="text-xs text-text-muted">
                        {t.stock_count} stocks · {(t.avg_confidence * 100).toFixed(0)}% conf
                        {t.category && ` · ${t.category}`}
                      </div>
                    </Link>
                  ))}
                </div>
              </div>

              {/* Open themes (bridging) */}
              <div className="bg-card rounded-lg border border-border p-4">
                <h3 className="text-sm font-semibold text-text-muted uppercase mb-3">Open Themes</h3>
                {results.open.length === 0 && <p className="text-text-muted text-sm">No matches</p>}
                <div className="space-y-2">
                  {results.open.map(t => (
                    <div key={t.theme_text} className="p-2 rounded hover:bg-card-hover transition-colors">
                      <div className="text-sm font-medium text-text-primary">{t.theme_text}</div>
                      <div className="text-xs text-text-muted">
                        {t.stock_count} stocks · {(t.avg_confidence * 100).toFixed(0)}% conf
                        {t.mapped_canonical && (
                          <> · <Link to={`/themes/${encodeURIComponent(t.mapped_canonical)}`} className="text-accent">→ {t.mapped_canonical}</Link></>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Stocks */}
              <div className="bg-card rounded-lg border border-border p-4">
                <h3 className="text-sm font-semibold text-text-muted uppercase mb-3">Stocks</h3>
                {results.stocks.length === 0 && <p className="text-text-muted text-sm">No matches</p>}
                <div className="space-y-2">
                  {results.stocks.map(s => (
                    <Link key={s.ticker} to={`/stocks/${s.ticker}`}
                      className="block p-2 rounded hover:bg-card-hover transition-colors">
                      <div className="text-sm font-medium text-accent">{s.ticker}</div>
                      <div className="text-xs text-text-muted">
                        {s.name} {s.market_cap && `· ${fmt(s.market_cap)}`}
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Leaderboards */}
      {!queryFromUrl && (
        loadingBoards ? (
          <div className="text-center py-12 text-text-muted">Loading...</div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 榜单A: Top Themes */}
            <div>
              <h2 className="text-lg font-semibold text-text-primary mb-3">
                🔥 Trending Themes
              </h2>
              <div className="bg-card rounded-lg border border-border overflow-hidden">
                <table className="min-w-full divide-y divide-border">
                  <thead className="bg-[#111]">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-text-muted uppercase">#</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-text-muted uppercase">Theme</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-text-muted uppercase">Regime</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-text-muted uppercase">Stocks</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-text-muted uppercase">Mkt Cap</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {topThemes.map((t, i) => (
                      <tr key={t.theme_name} className="hover:bg-card-hover transition-colors">
                        <td className="px-3 py-2 text-sm text-text-muted">{i + 1}</td>
                        <td className="px-3 py-2">
                          <Link to={`/themes/${encodeURIComponent(t.theme_name)}`}
                            className="text-sm font-medium text-accent hover:text-accent-hover">
                            {t.theme_name}
                          </Link>
                        </td>
                        <td className="px-3 py-2"><RegimeBadge regime={t.regime} /></td>
                        <td className="px-3 py-2 text-sm text-right text-text-secondary">{t.stock_count}</td>
                        <td className="px-3 py-2 text-sm text-right text-text-secondary">{fmt(t.total_market_cap)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 榜单B: High-Potential Emerging */}
            <div>
              <h2 className="text-lg font-semibold text-text-primary mb-3">
                🌱 High-Potential Emerging
              </h2>
              <div className="bg-card rounded-lg border border-border overflow-hidden">
                <table className="min-w-full divide-y divide-border">
                  <thead className="bg-[#111]">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-text-muted uppercase">#</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-text-muted uppercase">Theme</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-text-muted uppercase">Stocks</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-text-muted uppercase">Quality</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-text-muted uppercase">Distinct.</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {emerging.map((t, i) => (
                      <tr key={t.theme_text} className="hover:bg-card-hover transition-colors">
                        <td className="px-3 py-2 text-sm text-text-muted">{i + 1}</td>
                        <td className="px-3 py-2">
                          <div className="text-sm font-medium text-text-primary">{t.theme_text}</div>
                          {t.mapped_canonical && (
                            <Link to={`/themes/${encodeURIComponent(t.mapped_canonical)}`}
                              className="text-xs text-accent">
                              → {t.mapped_canonical}
                            </Link>
                          )}
                        </td>
                        <td className="px-3 py-2 text-sm text-right text-text-secondary">{t.stock_count}</td>
                        <td className="px-3 py-2 text-sm text-right">
                          <span className="text-positive">{(t.avg_quality * 100).toFixed(0)}</span>
                        </td>
                        <td className="px-3 py-2 text-sm text-right text-text-secondary">
                          {(t.avg_distinctiveness * 100).toFixed(0)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )
      )}
    </div>
  )
}
