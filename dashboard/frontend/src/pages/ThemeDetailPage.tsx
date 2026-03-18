import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { api } from '../api/client'
import type { ThemeDetail, HistoryPoint, DriftInfo, TradeabilityScore, OpenVariant, StockChange, RegimeHistoryPoint, ThemeTechnicals } from '../api/client'
import RegimeBadge from '../components/RegimeBadge'
import RegimeScoreGauge from '../components/RegimeScoreGauge'
import RegimeHistoryChart from '../components/RegimeHistoryChart'
import TradeabilityGauge from '../components/TradeabilityGauge'
import SourceBadge from '../components/SourceBadge'

function fmt(n: number | null | undefined): string {
  if (n == null) return '-'
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(1)}T`
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(0)}M`
  return `$${n.toFixed(0)}`
}

const TOOLTIP_STYLE = {
  contentStyle: { backgroundColor: '#141414', border: '1px solid #262626', borderRadius: '6px' },
  labelStyle: { color: '#a3a3a3' },
  itemStyle: { color: '#f5f5f5' },
}

export default function ThemeDetailPage() {
  const { name } = useParams<{ name: string }>()
  const [detail, setDetail] = useState<ThemeDetail | null>(null)
  const [history, setHistory] = useState<HistoryPoint[]>([])
  const [drift, setDrift] = useState<DriftInfo | null>(null)
  const [tradeability, setTradeability] = useState<TradeabilityScore | null>(null)
  const [openVariants, setOpenVariants] = useState<OpenVariant[]>([])
  const [stockChanges, setStockChanges] = useState<StockChange | null>(null)
  const [regimeHistory, setRegimeHistory] = useState<RegimeHistoryPoint[]>([])
  const [technicals, setTechnicals] = useState<ThemeTechnicals | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!name) return
    setLoading(true)
    Promise.all([
      api.themes.detail(name),
      api.themes.history(name),
      api.themes.drift(name),
      api.themes.tradeability(name),
      api.themes.openVariants(name),
      api.themes.stockChanges(name, 30),
      api.themes.regimeHistory(name).catch(() => []),
      api.themes.technicals(name).catch(() => null),
    ]).then(([d, h, dr, tr, ov, sc, rh, tech]) => {
      setDetail(d)
      setHistory(h)
      setDrift(dr)
      setTradeability(tr)
      setOpenVariants(ov)
      setStockChanges(sc)
      setRegimeHistory(rh)
      setTechnicals(tech)
    }).finally(() => setLoading(false))
  }, [name])

  if (loading) return <div className="text-center py-12 text-text-muted">Loading...</div>
  if (!detail) return <div className="text-center py-12 text-text-muted">Theme not found</div>

  const subThemes = drift?.sub_theme_shift ? Object.entries(drift.sub_theme_shift) : []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold text-text-primary capitalize">{detail.theme_name}</h1>
        <RegimeBadge regime={detail.regime} score={detail.regime_score}
          direction={detail.regime_direction} watchStatus={detail.watch_status} />
        {tradeability && (
          <span className="ml-auto text-sm text-text-muted">
            Tradeability: <span className="text-lg font-bold text-accent">{Math.round(tradeability.tradeability_score * 100)}</span>
          </span>
        )}
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Stocks', value: detail.stock_count },
          { label: 'Market Cap', value: fmt(detail.total_market_cap) },
          { label: 'Avg Confidence', value: `${(detail.avg_confidence * 100).toFixed(0)}%` },
          { label: 'Drift Score', value: drift ? drift.drift_score.toFixed(3) : '-' },
        ].map(({ label, value }) => (
          <div key={label} className="bg-card rounded-lg border border-border p-4">
            <div className="text-xs text-text-muted uppercase">{label}</div>
            <div className="text-xl font-semibold text-text-primary mt-1">{value}</div>
          </div>
        ))}
      </div>

      {/* Regime Gauge + Technicals */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {detail.regime_score != null && (
          <div className="bg-card rounded-lg border border-border p-4">
            <h3 className="text-sm font-medium text-text-secondary mb-2">Regime Score</h3>
            <RegimeScoreGauge
              score={detail.regime_score}
              label={detail.regime}
              direction={detail.regime_direction}
              watchStatus={detail.watch_status}
            />
          </div>
        )}

        {technicals && (
          <div className="bg-card rounded-lg border border-border p-4">
            <h3 className="text-sm font-medium text-text-secondary mb-3">Theme Technicals</h3>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Avg MA20 Distance', value: technicals.avg_ma20_distance_pct != null ? `${technicals.avg_ma20_distance_pct > 0 ? '+' : ''}${technicals.avg_ma20_distance_pct.toFixed(1)}%` : '-' },
                { label: 'Stocks Above MA20', value: technicals.pct_above_ma20 != null ? `${(technicals.pct_above_ma20 * 100).toFixed(0)}%` : '-' },
                { label: 'Volume Trend', value: technicals.avg_volume_trend != null ? technicals.avg_volume_trend.toFixed(3) : '-' },
                { label: 'Analyst Upside', value: technicals.avg_analyst_upside_pct != null ? `${technicals.avg_analyst_upside_pct > 0 ? '+' : ''}${technicals.avg_analyst_upside_pct.toFixed(1)}%` : '-' },
                { label: 'Earnings Surprises', value: technicals.avg_positive_surprises != null ? `${technicals.avg_positive_surprises.toFixed(1)} / 4` : '-' },
              ].map(({ label, value }) => (
                <div key={label}>
                  <div className="text-xs text-text-muted">{label}</div>
                  <div className="text-sm font-semibold text-text-primary">{value}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Regime History Chart */}
      {regimeHistory.length > 0 && (
        <div className="bg-card rounded-lg border border-border p-4">
          <h2 className="text-sm font-medium text-text-secondary mb-3">Regime Score Over Time</h2>
          <RegimeHistoryChart data={regimeHistory} />
        </div>
      )}

      {/* Tradeability Gauge + Recent Changes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {tradeability && (
          <TradeabilityGauge
            components={tradeability.components}
            score={tradeability.tradeability_score}
          />
        )}

        {/* Recent Stock Changes */}
        {stockChanges && (stockChanges.entrants.length > 0 || stockChanges.exits.length > 0) && (
          <div className="bg-card rounded-lg border border-border p-4">
            <h3 className="text-sm font-medium text-text-primary mb-3">
              Stock Changes (last {stockChanges.period_days}d)
            </h3>
            {stockChanges.entrants.length > 0 && (
              <div className="mb-3">
                <div className="text-xs text-text-muted uppercase mb-1">New Entrants</div>
                <div className="flex flex-wrap gap-1">
                  {stockChanges.entrants.map(t => (
                    <Link key={t} to={`/stocks/${t}`}
                      className="text-xs px-2 py-0.5 bg-green-900/30 text-green-400 rounded">
                      +{t}
                    </Link>
                  ))}
                </div>
              </div>
            )}
            {stockChanges.exits.length > 0 && (
              <div>
                <div className="text-xs text-text-muted uppercase mb-1">Exits</div>
                <div className="flex flex-wrap gap-1">
                  {stockChanges.exits.map(t => (
                    <Link key={t} to={`/stocks/${t}`}
                      className="text-xs px-2 py-0.5 bg-red-900/30 text-red-400 rounded">
                      -{t}
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Related Open Themes */}
      {openVariants.length > 0 && (
        <div className="bg-card rounded-lg border border-border p-4">
          <h2 className="text-sm font-medium text-text-secondary mb-3">
            Related Open Themes ({openVariants.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {openVariants.map(ov => (
              <div key={ov.theme_text} className="p-3 bg-card-hover rounded-lg">
                <div className="text-sm font-medium text-text-primary">{ov.theme_text}</div>
                <div className="text-xs text-text-muted mt-1">
                  {ov.stock_count} stocks · {(ov.avg_confidence * 100).toFixed(0)}% conf
                  · {(ov.avg_distinctiveness * 100).toFixed(0)}% dist
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* History chart */}
      {history.length > 0 && (
        <div className="bg-card rounded-lg border border-border p-4">
          <h2 className="text-sm font-medium text-text-secondary mb-3">Stock Count Over Time</h2>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="snapshot_date" tick={{ fontSize: 11, fill: '#a3a3a3' }} stroke="#333" />
              <YAxis tick={{ fontSize: 11, fill: '#a3a3a3' }} stroke="#333" />
              <Tooltip {...TOOLTIP_STYLE} />
              <Line type="monotone" dataKey="stock_count" stroke="#0693e3" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Drift — sub-theme shift */}
      {subThemes.length > 0 && (
        <div className="bg-card rounded-lg border border-border p-4">
          <h2 className="text-sm font-medium text-text-secondary mb-3">Sub-Theme Composition Shift</h2>
          <div className="space-y-2">
            {subThemes.map(([child, data]) => (
              <div key={child} className="flex items-center gap-3">
                <Link to={`/themes/${encodeURIComponent(child)}`} className="w-40 text-sm text-accent hover:text-accent-hover truncate">
                  {child}
                </Link>
                <div className="flex-1 flex items-center gap-2">
                  <div className="w-16 text-right text-xs text-text-muted">{(data.t0_pct * 100).toFixed(0)}%</div>
                  <div className="flex-1 h-2 bg-card-hover rounded-full overflow-hidden relative">
                    <div className="absolute inset-y-0 left-0 bg-blue-800 rounded-full" style={{ width: `${data.t0_pct * 100}%` }} />
                    <div className="absolute inset-y-0 left-0 bg-accent rounded-full" style={{ width: `${data.t1_pct * 100}%` }} />
                  </div>
                  <div className="w-16 text-xs text-text-secondary">{(data.t1_pct * 100).toFixed(0)}%</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Weekly drift chart */}
      {drift && drift.weekly_drift.length > 0 && (
        <div className="bg-card rounded-lg border border-border p-4">
          <h2 className="text-sm font-medium text-text-secondary mb-3">Weekly Basket Drift (Jaccard)</h2>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={drift.weekly_drift}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#a3a3a3' }} stroke="#333" />
              <YAxis tick={{ fontSize: 11, fill: '#a3a3a3' }} stroke="#333" domain={[0, 1]} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Area type="monotone" dataKey="jaccard" stroke="#ef4444" fill="#3b1111" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Stock list */}
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-medium text-text-secondary">Stocks ({detail.stocks.length})</h2>
        </div>
        <table className="min-w-full divide-y divide-border">
          <thead className="bg-[#111]">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-text-muted uppercase">Ticker</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-text-muted uppercase">Name</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-text-muted uppercase">Market Cap</th>
              <th className="px-4 py-2 text-right text-xs font-medium text-text-muted uppercase">Confidence</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-text-muted uppercase">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {detail.stocks.map((s) => (
              <tr key={s.ticker} className="hover:bg-card-hover transition-colors">
                <td className="px-4 py-2">
                  <Link to={`/stocks/${s.ticker}`} className="text-sm font-medium text-accent hover:text-accent-hover">
                    {s.ticker}
                  </Link>
                </td>
                <td className="px-4 py-2 text-sm text-text-secondary">{s.name}</td>
                <td className="px-4 py-2 text-sm text-right text-text-secondary">{fmt(s.market_cap)}</td>
                <td className="px-4 py-2 text-sm text-right text-text-secondary">{(s.confidence * 100).toFixed(0)}%</td>
                <td className="px-4 py-2"><SourceBadge source={s.source} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
