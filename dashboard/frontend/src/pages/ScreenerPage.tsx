import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { ScreenerResult, ScreenerFilters } from '../api/client'
import FilterPanel from '../components/FilterPanel'

function fmt(n: number | null | undefined): string {
  if (n == null) return '-'
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(1)}T`
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(0)}M`
  return `$${n.toFixed(0)}`
}

export default function ScreenerPage() {
  const [results, setResults] = useState<ScreenerResult[]>([])
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)

  const handleApply = async (filters: ScreenerFilters) => {
    setLoading(true)
    setHasSearched(true)
    try {
      const data = await api.screener(filters)
      setResults(data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-text-primary mb-6">Stock Screener</h1>

      <div className="flex gap-6">
        {/* Filter sidebar */}
        <div className="w-64 shrink-0">
          <div className="bg-card rounded-lg border border-border p-4 sticky top-20">
            <FilterPanel onApply={handleApply} />
          </div>
        </div>

        {/* Results */}
        <div className="flex-1">
          {loading ? (
            <div className="text-center py-12 text-text-muted">Filtering...</div>
          ) : !hasSearched ? (
            <div className="text-center py-12 text-text-muted">
              Configure filters and click Apply to find stocks
            </div>
          ) : results.length === 0 ? (
            <div className="text-center py-12 text-text-muted">No stocks match the filters</div>
          ) : (
            <>
              <div className="text-sm text-text-muted mb-3">{results.length} results</div>
              <div className="bg-card rounded-lg border border-border overflow-hidden">
                <table className="min-w-full divide-y divide-border">
                  <thead className="bg-[#111]">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Ticker</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Name</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Sector</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-text-muted uppercase">Market Cap</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Top Themes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {results.map(s => (
                      <tr key={s.ticker} className="hover:bg-card-hover transition-colors">
                        <td className="px-4 py-3">
                          <Link to={`/stocks/${s.ticker}`}
                            className="text-sm font-medium text-accent hover:text-accent-hover">
                            {s.ticker}
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-sm text-text-secondary">{s.name}</td>
                        <td className="px-4 py-3 text-sm text-text-muted">{s.sector || '-'}</td>
                        <td className="px-4 py-3 text-sm text-right text-text-secondary">{fmt(s.market_cap)}</td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-1">
                            {s.themes?.slice(0, 3).map(t => (
                              <span key={t.name}
                                className="text-xs px-1.5 py-0.5 bg-card-hover rounded text-text-secondary">
                                {t.name} ({(t.confidence * 100).toFixed(0)}%)
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
