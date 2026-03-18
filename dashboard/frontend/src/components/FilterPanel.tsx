import { useState } from 'react'
import type { ScreenerFilters } from '../api/client'

interface FilterPanelProps {
  onApply: (filters: ScreenerFilters) => void
  themes?: string[]
  narratives?: string[]
  sectors?: string[]
}

export default function FilterPanel({ onApply, sectors = [] }: FilterPanelProps) {
  const [filters, setFilters] = useState<ScreenerFilters>({
    themes: [],
    narratives: [],
    sources: [],
    sectors: [],
    sort_by: 'market_cap',
    limit: 100,
  })

  const update = (key: keyof ScreenerFilters, value: unknown) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const toggleArrayItem = (key: 'themes' | 'narratives' | 'sources' | 'sectors', item: string) => {
    setFilters(prev => {
      const arr = (prev[key] as string[]) || []
      return {
        ...prev,
        [key]: arr.includes(item) ? arr.filter(x => x !== item) : [...arr, item],
      }
    })
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Filters</h3>

      {/* Confidence slider */}
      <div>
        <label className="text-xs text-text-muted block mb-1">
          Min Confidence: {(filters.min_confidence || 0).toFixed(1)}
        </label>
        <input
          type="range" min="0" max="1" step="0.1"
          value={filters.min_confidence || 0}
          onChange={e => update('min_confidence', parseFloat(e.target.value) || undefined)}
          className="w-full accent-accent"
        />
      </div>

      {/* Distinctiveness slider */}
      <div>
        <label className="text-xs text-text-muted block mb-1">
          Min Distinctiveness: {(filters.min_distinctiveness || 0).toFixed(1)}
        </label>
        <input
          type="range" min="0" max="1" step="0.1"
          value={filters.min_distinctiveness || 0}
          onChange={e => update('min_distinctiveness', parseFloat(e.target.value) || undefined)}
          className="w-full accent-accent"
        />
      </div>

      {/* Freshness slider */}
      <div>
        <label className="text-xs text-text-muted block mb-1">
          Min Freshness: {(filters.min_freshness || 0).toFixed(1)}
        </label>
        <input
          type="range" min="0" max="1" step="0.1"
          value={filters.min_freshness || 0}
          onChange={e => update('min_freshness', parseFloat(e.target.value) || undefined)}
          className="w-full accent-accent"
        />
      </div>

      {/* Source checkboxes */}
      <div>
        <label className="text-xs text-text-muted block mb-1">Sources</label>
        <div className="space-y-1">
          {['llm', 'narrative', '13f'].map(src => (
            <label key={src} className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
              <input
                type="checkbox"
                checked={(filters.sources || []).includes(src)}
                onChange={() => toggleArrayItem('sources', src)}
                className="accent-accent"
              />
              {src}
            </label>
          ))}
        </div>
      </div>

      {/* Sector select */}
      {sectors.length > 0 && (
        <div>
          <label className="text-xs text-text-muted block mb-1">Sector</label>
          <select
            className="w-full bg-card-hover border border-border rounded px-2 py-1.5 text-sm text-text-primary"
            value=""
            onChange={e => {
              if (e.target.value) toggleArrayItem('sectors', e.target.value)
            }}
          >
            <option value="">Add sector...</option>
            {sectors.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <div className="flex flex-wrap gap-1 mt-1">
            {(filters.sectors || []).map(s => (
              <span
                key={s}
                className="text-xs bg-card-hover text-text-secondary px-2 py-0.5 rounded cursor-pointer hover:bg-border"
                onClick={() => toggleArrayItem('sectors', s)}
              >
                {s} ×
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Market cap */}
      <div>
        <label className="text-xs text-text-muted block mb-1">Min Market Cap ($B)</label>
        <input
          type="number" min="0" step="1"
          className="w-full bg-card-hover border border-border rounded px-2 py-1.5 text-sm text-text-primary"
          placeholder="0"
          onChange={e => update('min_market_cap', e.target.value ? parseFloat(e.target.value) * 1e9 : undefined)}
        />
      </div>

      {/* Toggles */}
      <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
        <input
          type="checkbox"
          checked={filters.has_13f_activity || false}
          onChange={e => update('has_13f_activity', e.target.checked)}
          className="accent-accent"
        />
        Has 13F activity
      </label>

      <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
        <input
          type="checkbox"
          checked={filters.near_promotion || false}
          onChange={e => update('near_promotion', e.target.checked)}
          className="accent-accent"
        />
        Near promotion candidate
      </label>

      {/* Apply button */}
      <button
        onClick={() => onApply(filters)}
        className="w-full px-4 py-2 bg-accent text-white rounded-md text-sm font-medium hover:bg-accent-hover transition-colors"
      >
        Apply Filters
      </button>
    </div>
  )
}
