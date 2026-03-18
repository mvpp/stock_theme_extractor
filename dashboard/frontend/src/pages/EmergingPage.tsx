import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { EmergingTheme } from '../api/client'

export default function EmergingPage() {
  const [themes, setThemes] = useState<EmergingTheme[]>([])
  const [loading, setLoading] = useState(true)

  // Promote/dismiss state
  const [promoting, setPromoting] = useState<string | null>(null)
  const [form, setForm] = useState({ canonical_name: '', parent_theme: '', category: '' })

  useEffect(() => {
    api.themes.emerging(30).then(setThemes).finally(() => setLoading(false))
  }, [])

  const handlePromote = async (themeText: string) => {
    if (!form.canonical_name.trim()) return
    await api.promotions.promote({
      open_theme_text: themeText,
      canonical_name: form.canonical_name,
      parent_theme: form.parent_theme || undefined,
      category: form.category || undefined,
    })
    setThemes(prev => prev.filter(t => t.theme_text !== themeText))
    setPromoting(null)
    setForm({ canonical_name: '', parent_theme: '', category: '' })
  }

  const handleDismiss = async (themeText: string) => {
    await api.promotions.dismiss(themeText)
    setThemes(prev => prev.filter(t => t.theme_text !== themeText))
  }

  if (loading) return <div className="text-center py-12 text-text-muted">Loading...</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text-primary">Emerging Themes</h1>
        <Link to="/promotions" className="text-sm text-accent hover:text-accent-hover">
          Promotion History →
        </Link>
      </div>

      <div className="space-y-4">
        {themes.map(t => {
          const tickers = t.tickers ? t.tickers.split(', ').slice(0, 5) : []
          return (
            <div key={t.theme_text} className="bg-card rounded-lg border border-border p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="text-base font-semibold text-text-primary">{t.theme_text}</h3>
                  <div className="flex flex-wrap gap-3 mt-2 text-sm text-text-secondary">
                    <span>{t.stock_count} stocks</span>
                    <span>Quality: <span className="text-positive">{(t.avg_quality * 100).toFixed(0)}</span></span>
                    <span>Conf: {(t.avg_confidence * 100).toFixed(0)}%</span>
                    <span>Dist: {(t.avg_distinctiveness * 100).toFixed(0)}%</span>
                    {t.avg_freshness != null && (
                      <span>Fresh: {(t.avg_freshness * 100).toFixed(0)}%</span>
                    )}
                  </div>

                  {/* Representative tickers */}
                  <div className="flex gap-2 mt-2">
                    {tickers.map(ticker => (
                      <Link key={ticker} to={`/stocks/${ticker}`}
                        className="text-xs px-2 py-0.5 bg-card-hover rounded text-accent hover:text-accent-hover">
                        {ticker}
                      </Link>
                    ))}
                  </div>

                  {/* Mapping info */}
                  <div className="mt-2 text-xs text-text-muted">
                    {t.mapped_canonical ? (
                      <>
                        Nearest: <Link to={`/themes/${encodeURIComponent(t.mapped_canonical)}`}
                          className="text-accent">{t.mapped_canonical}</Link>
                        {' '}(similarity: {(t.avg_mapped_similarity * 100).toFixed(0)}%)
                      </>
                    ) : (
                      'No canonical mapping'
                    )}
                    {t.recommended_branch && (
                      <span className="ml-2">· Branch: {t.recommended_branch}</span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2 ml-4">
                  <button
                    onClick={() => setPromoting(promoting === t.theme_text ? null : t.theme_text)}
                    className="px-3 py-1 text-sm rounded border text-green-400 bg-green-900/30 border-green-800 hover:bg-green-900/50"
                  >
                    Promote
                  </button>
                  <button
                    onClick={() => handleDismiss(t.theme_text)}
                    className="px-3 py-1 text-sm rounded border text-red-400 bg-red-900/30 border-red-800 hover:bg-red-900/50"
                  >
                    Dismiss
                  </button>
                </div>
              </div>

              {/* Promote form */}
              {promoting === t.theme_text && (
                <div className="mt-3 p-3 bg-card-hover rounded border border-border-emphasis">
                  <div className="grid grid-cols-3 gap-2">
                    <input
                      placeholder="Canonical name *"
                      value={form.canonical_name}
                      onChange={e => setForm(p => ({ ...p, canonical_name: e.target.value }))}
                      className="bg-card border border-border rounded px-2 py-1 text-sm text-text-primary placeholder:text-text-muted"
                    />
                    <input
                      placeholder="Parent theme"
                      value={form.parent_theme}
                      onChange={e => setForm(p => ({ ...p, parent_theme: e.target.value }))}
                      className="bg-card border border-border rounded px-2 py-1 text-sm text-text-primary placeholder:text-text-muted"
                    />
                    <input
                      placeholder="Category"
                      value={form.category}
                      onChange={e => setForm(p => ({ ...p, category: e.target.value }))}
                      className="bg-card border border-border rounded px-2 py-1 text-sm text-text-primary placeholder:text-text-muted"
                    />
                  </div>
                  <button
                    onClick={() => handlePromote(t.theme_text)}
                    className="mt-2 px-4 py-1 bg-accent text-white rounded text-sm hover:bg-accent-hover"
                  >
                    Confirm Promotion
                  </button>
                </div>
              )}
            </div>
          )
        })}
        {themes.length === 0 && (
          <div className="text-center py-12 text-text-muted">No emerging themes found</div>
        )}
      </div>
    </div>
  )
}
