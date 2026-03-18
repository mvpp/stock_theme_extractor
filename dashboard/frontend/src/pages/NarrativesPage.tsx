import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Treemap, ResponsiveContainer } from 'recharts'
import { api } from '../api/client'
import type { NarrativeTheme, HeatmapCategory, InvestorHolding } from '../api/client'

// Custom treemap content renderer
function TreemapContent(props: any) {
  const { x, y, width, height, name, stock_count } = props
  if (width < 40 || height < 25) return null
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={3}
        fill="#1a1a1a" stroke="#333" strokeWidth={1} />
      <text x={x + 6} y={y + 14} fontSize={11} fill="#f5f5f5" fontWeight={500}>
        {width > 80 ? name : name?.slice(0, 8)}
      </text>
      <text x={x + 6} y={y + 27} fontSize={10} fill="#a3a3a3">
        {stock_count}
      </text>
    </g>
  )
}

export default function NarrativesPage() {
  const [narratives, setNarratives] = useState<NarrativeTheme[]>([])
  const [heatmap, setHeatmap] = useState<HeatmapCategory[]>([])
  const [holdings, setHoldings] = useState<InvestorHolding[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'narratives' | 'heatmap' | '13f'>('narratives')

  useEffect(() => {
    Promise.all([
      api.narratives.list(),
      api.narratives.heatmap(),
      api.investors.activity(30),
    ]).then(([n, h, ih]) => {
      setNarratives(n)
      setHeatmap(h)
      setHoldings(ih)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-text-muted">Loading...</div>

  // Prepare treemap data
  const treemapData = heatmap.map(cat => ({
    name: cat.name,
    children: cat.children.map(c => ({
      name: c.name,
      size: c.stock_count,
      stock_count: c.stock_count,
    })),
  }))

  return (
    <div>
      <h1 className="text-2xl font-bold text-text-primary mb-6">Narratives & Smart Money</h1>

      {/* Tabs */}
      <div className="flex gap-1 bg-[#111] rounded-lg p-0.5 mb-6 w-fit">
        {[
          { id: 'narratives' as const, label: 'Narrative Table' },
          { id: 'heatmap' as const, label: 'Heatmap' },
          { id: '13f' as const, label: '13F Activity' },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
              tab === t.id ? 'bg-card-hover text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Narrative Table */}
      {tab === 'narratives' && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-[#111]">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Narrative</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-text-muted uppercase">Stocks</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-text-muted uppercase">Confidence</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-text-muted uppercase">Distinctiveness</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-text-muted uppercase">Freshness</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {narratives.map(n => (
                <tr key={n.theme_text} className="hover:bg-card-hover transition-colors">
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-text-primary">{n.theme_text}</div>
                    <div className="text-xs text-text-muted mt-0.5">
                      {n.tickers.split(', ').slice(0, 5).map(t => (
                        <Link key={t} to={`/stocks/${t}`} className="text-accent mr-1">{t}</Link>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-text-secondary">{n.stock_count}</td>
                  <td className="px-4 py-3 text-sm text-right text-text-secondary">
                    {(n.avg_confidence * 100).toFixed(0)}%
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-text-secondary">
                    {(n.avg_distinctiveness * 100).toFixed(0)}%
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-text-secondary">
                    {n.avg_freshness != null ? `${(n.avg_freshness * 100).toFixed(0)}%` : '-'}
                  </td>
                </tr>
              ))}
              {narratives.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-text-muted">No narratives found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Heatmap (Treemap) */}
      {tab === 'heatmap' && (
        <div className="bg-card rounded-lg border border-border p-4">
          <h3 className="text-sm font-semibold text-text-muted uppercase mb-3">
            Narrative Distribution by Category
          </h3>
          {treemapData.length > 0 ? (
            <ResponsiveContainer width="100%" height={400}>
              <Treemap
                data={treemapData}
                dataKey="size"
                aspectRatio={4 / 3}
                stroke="#262626"
                content={<TreemapContent />}
              />
            </ResponsiveContainer>
          ) : (
            <div className="text-center py-12 text-text-muted">No heatmap data available</div>
          )}
          {/* Legend: categories list */}
          <div className="flex flex-wrap gap-3 mt-4">
            {heatmap.map(cat => (
              <span key={cat.name} className="text-xs text-text-secondary">
                <span className="font-medium text-text-primary">{cat.name}</span>
                {' '}({cat.total_stocks} stocks, {cat.children.length} narratives)
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 13F Activity */}
      {tab === '13f' && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-[#111]">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Investor</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Stock</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-text-muted uppercase">Action</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-text-muted uppercase">Change</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-text-muted uppercase">Filing Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {holdings.map((h, i) => {
                const changeColor = ['new_position', 'added', 'significantly_added'].includes(h.change_type)
                  ? 'text-positive' : ['sold_entire', 'trimmed', 'significantly_trimmed'].includes(h.change_type)
                  ? 'text-negative' : 'text-text-secondary'
                return (
                  <tr key={i} className="hover:bg-card-hover transition-colors">
                    <td className="px-4 py-3 text-sm text-text-primary">{h.investor_name}</td>
                    <td className="px-4 py-3">
                      <Link to={`/stocks/${h.ticker}`} className="text-sm text-accent hover:text-accent-hover">
                        {h.ticker}
                      </Link>
                      {h.name && <span className="text-xs text-text-muted ml-1">{h.name}</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-sm font-medium ${changeColor}`}>
                        {h.change_type.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-text-secondary">
                      {h.pct_change != null ? `${h.pct_change > 0 ? '+' : ''}${(h.pct_change * 100).toFixed(0)}%` : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-text-muted">{h.filing_date || '-'}</td>
                  </tr>
                )
              })}
              {holdings.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-text-muted">No 13F activity found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
