const SOURCE_STYLES: Record<string, string> = {
  llm: 'bg-blue-900/40 text-blue-400',
  narrative: 'bg-amber-900/40 text-amber-400',
  '13f': 'bg-purple-900/40 text-purple-400',
  patent: 'bg-cyan-900/40 text-cyan-400',
  news: 'bg-emerald-900/40 text-emerald-400',
  sic: 'bg-gray-800/40 text-gray-400',
  social: 'bg-pink-900/40 text-pink-400',
}

export default function SourceBadge({ source }: { source: string }) {
  const style = SOURCE_STYLES[source] || 'bg-card-hover text-text-muted'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${style}`}>
      {source}
    </span>
  )
}
