import { useEffect, useState } from 'react'
import { api, type DataFreshnessItem } from '../api/client'

export default function DataFreshnessBanner() {
  const [staleItems, setStaleItems] = useState<DataFreshnessItem[]>([])

  useEffect(() => {
    api.dataFreshness()
      .then(items => setStaleItems(items.filter(i => i.is_stale && i.last_run !== null)))
      .catch(() => {}) // silently fail — banner is non-critical
  }, [])

  if (staleItems.length === 0) return null

  const names = staleItems.map(i => {
    const name = i.pipeline_name.replace('_pipeline', '').replace('_', ' ')
    return name.charAt(0).toUpperCase() + name.slice(1)
  })

  return (
    <div className="bg-amber-900/30 border-b border-amber-700/50 px-4 py-2 text-amber-300 text-xs text-center">
      {names.join(', ')} data may be outdated.
      {staleItems[0]?.last_run && (
        <span className="text-amber-400/70 ml-1">
          Last updated: {new Date(staleItems[0].last_run).toLocaleDateString()}
        </span>
      )}
    </div>
  )
}
