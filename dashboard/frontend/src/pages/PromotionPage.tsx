import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { PromotionCandidate } from '../api/client'

export default function PromotionPage() {
  const [candidates, setCandidates] = useState<PromotionCandidate[]>([])
  const [loading, setLoading] = useState(true)
  const [promoting, setPromoting] = useState<string | null>(null)
  const [form, setForm] = useState({ canonical_name: '', parent_theme: '', category: '' })

  useEffect(() => {
    api.promotions.candidates().then(setCandidates).finally(() => setLoading(false))
  }, [])

  const handlePromote = async (themeText: string) => {
    await api.promotions.promote({
      open_theme_text: themeText,
      canonical_name: form.canonical_name || themeText,
      parent_theme: form.parent_theme || undefined,
      category: form.category || undefined,
    })
    setCandidates((prev) => prev.filter((c) => c.theme_text !== themeText))
    setPromoting(null)
    setForm({ canonical_name: '', parent_theme: '', category: '' })
  }

  const handleDismiss = async (themeText: string) => {
    await api.promotions.dismiss(themeText)
    setCandidates((prev) => prev.filter((c) => c.theme_text !== themeText))
  }

  if (loading) return <div className="text-center py-12 text-text-muted">Loading...</div>

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-text-primary">Theme Promotion</h1>
      <p className="text-sm text-text-muted">
        Open themes appearing across multiple stocks with high quality. Promote them to canonical or dismiss.
      </p>

      {candidates.length === 0 ? (
        <div className="text-center py-8 text-text-muted">No promotion candidates</div>
      ) : (
        <div className="space-y-3">
          {candidates.map((c) => (
            <div key={c.theme_text} className="bg-card rounded-lg border border-border p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-sm font-medium text-text-primary">{c.theme_text}</h3>
                  <div className="flex gap-4 mt-1 text-xs text-text-muted">
                    <span>{c.stock_count} stocks</span>
                    <span>conf: {(c.avg_confidence * 100).toFixed(0)}%</span>
                    <span>dist: {(c.avg_distinctiveness * 100).toFixed(0)}%</span>
                    {c.mapped_canonical && (
                      <span>nearest: {c.mapped_canonical}</span>
                    )}
                  </div>
                  <div className="mt-1 text-xs text-text-muted truncate max-w-lg">{c.tickers}</div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPromoting(promoting === c.theme_text ? null : c.theme_text)}
                    className="px-3 py-1 text-xs font-medium text-green-400 bg-green-900/30 border border-green-800 rounded hover:bg-green-900/50 transition-colors"
                  >
                    Promote
                  </button>
                  <button
                    onClick={() => handleDismiss(c.theme_text)}
                    className="px-3 py-1 text-xs font-medium text-red-400 bg-red-900/30 border border-red-800 rounded hover:bg-red-900/50 transition-colors"
                  >
                    Dismiss
                  </button>
                </div>
              </div>

              {promoting === c.theme_text && (
                <div className="mt-3 pt-3 border-t border-border grid grid-cols-3 gap-3">
                  <input
                    type="text"
                    placeholder="Canonical name"
                    value={form.canonical_name}
                    onChange={(e) => setForm({ ...form, canonical_name: e.target.value })}
                    className="px-2 py-1.5 text-sm bg-card-hover border border-border-emphasis rounded text-text-primary placeholder:text-text-muted"
                  />
                  <input
                    type="text"
                    placeholder="Parent theme (optional)"
                    value={form.parent_theme}
                    onChange={(e) => setForm({ ...form, parent_theme: e.target.value })}
                    className="px-2 py-1.5 text-sm bg-card-hover border border-border-emphasis rounded text-text-primary placeholder:text-text-muted"
                  />
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Category"
                      value={form.category}
                      onChange={(e) => setForm({ ...form, category: e.target.value })}
                      className="flex-1 px-2 py-1.5 text-sm bg-card-hover border border-border-emphasis rounded text-text-primary placeholder:text-text-muted"
                    />
                    <button
                      onClick={() => handlePromote(c.theme_text)}
                      className="px-3 py-1.5 text-xs font-medium text-white bg-green-600 rounded hover:bg-green-700 transition-colors"
                    >
                      Confirm
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
