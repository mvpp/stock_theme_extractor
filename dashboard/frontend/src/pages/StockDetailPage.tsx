import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api/client'
import type { StockDetail } from '../api/client'
import SourceBadge from '../components/SourceBadge'

function fmt(n: number | null | undefined): string {
  if (n == null) return '-'
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(1)}T`
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(0)}M`
  return `$${n.toFixed(0)}`
}

export default function StockDetailPage() {
  const { ticker } = useParams<{ ticker: string }>()
  const [stock, setStock] = useState<StockDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!ticker) return
    setLoading(true)
    api.stocks.detail(ticker).then(setStock).finally(() => setLoading(false))
  }, [ticker])

  if (loading) return <div className="text-center py-12 text-text-muted">Loading...</div>
  if (!stock) return <div className="text-center py-12 text-text-muted">Stock not found</div>

  const canonical = stock.themes.filter((t) => t.tier === 'canonical')
  const open = stock.themes.filter((t) => t.tier === 'open')
  const holdings = stock.investor_holdings || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-text-primary">{stock.ticker}</h1>
        <p className="text-text-secondary">{stock.name}</p>
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Sector', value: stock.sector || '-' },
          { label: 'Industry', value: stock.industry || '-' },
          { label: 'Market Cap', value: fmt(stock.market_cap) },
        ].map(({ label, value }) => (
          <div key={label} className="bg-card rounded-lg border border-border p-4">
            <div className="text-xs text-text-muted uppercase">{label}</div>
            <div className="text-lg font-semibold text-text-primary mt-1">{value}</div>
          </div>
        ))}
      </div>

      {/* Canonical themes */}
      {canonical.length > 0 && (
        <div className="bg-card rounded-lg border border-border p-4">
          <h2 className="text-sm font-medium text-text-secondary mb-3">Canonical Themes ({canonical.length})</h2>
          <div className="space-y-2">
            {canonical.map((t) => (
              <div key={t.name}>
                <div className="flex items-center gap-3">
                  <Link to={`/themes/${encodeURIComponent(t.name)}`} className="text-sm text-accent hover:text-accent-hover w-48 truncate">
                    {t.name}
                  </Link>
                  <div className="flex-1 h-2 bg-card-hover rounded-full overflow-hidden">
                    <div className="h-full bg-accent rounded-full" style={{ width: `${t.confidence * 100}%` }} />
                  </div>
                  <span className="text-xs text-text-muted w-12 text-right">{(t.confidence * 100).toFixed(0)}%</span>
                  <SourceBadge source={t.source} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Open themes (enriched) */}
      {open.length > 0 && (
        <div className="bg-card rounded-lg border border-border p-4">
          <h2 className="text-sm font-medium text-text-secondary mb-3">Open Themes ({open.length})</h2>
          <div className="space-y-3">
            {open.map((t, i) => (
              <div key={i} className="border border-border rounded-lg p-3 hover:bg-card-hover transition-colors">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-text-primary flex-1">{t.name}</span>
                  <div className="w-24 h-2 bg-card-hover rounded-full overflow-hidden">
                    <div className="h-full bg-amber-400 rounded-full" style={{ width: `${t.confidence * 100}%` }} />
                  </div>
                  <span className="text-xs text-text-muted w-12 text-right">{(t.confidence * 100).toFixed(0)}%</span>
                  <SourceBadge source={t.source} />
                </div>
                <div className="flex gap-3 mt-1.5 text-xs text-text-muted">
                  {t.distinctiveness != null && (
                    <span>Dist: {(t.distinctiveness * 100).toFixed(0)}%</span>
                  )}
                  {t.freshness != null && (
                    <span>Fresh: {(t.freshness * 100).toFixed(0)}%</span>
                  )}
                  {t.quality_score != null && (
                    <span>Quality: <span className="text-positive">{(t.quality_score * 100).toFixed(0)}</span></span>
                  )}
                  {t.mapped_canonical && (
                    <span>→ <Link to={`/themes/${encodeURIComponent(t.mapped_canonical)}`} className="text-accent">{t.mapped_canonical}</Link></span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 13F Smart Money */}
      {holdings.length > 0 && (
        <div className="bg-card rounded-lg border border-border p-4">
          <h2 className="text-sm font-medium text-text-secondary mb-3">
            Smart Money — 13F Activity ({holdings.length})
          </h2>
          <div className="space-y-2">
            {holdings.map((h, i) => {
              const isPositive = ['new_position', 'added', 'significantly_added'].includes(h.change_type)
              const isNegative = ['sold_entire', 'trimmed', 'significantly_trimmed'].includes(h.change_type)
              return (
                <div key={i} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                  <div>
                    <span className="text-sm font-medium text-text-primary">{h.investor_name}</span>
                    <span className="text-xs text-text-muted ml-2">({h.investor_short})</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`text-sm font-medium ${
                      isPositive ? 'text-positive' : isNegative ? 'text-negative' : 'text-text-secondary'
                    }`}>
                      {h.change_type.replace(/_/g, ' ')}
                    </span>
                    {h.pct_change != null && (
                      <span className="text-xs text-text-muted">
                        {h.pct_change > 0 ? '+' : ''}{(h.pct_change * 100).toFixed(0)}%
                      </span>
                    )}
                    {h.filing_date && (
                      <span className="text-xs text-text-muted">{h.filing_date}</span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
