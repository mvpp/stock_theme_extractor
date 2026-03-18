const REGIME_STYLES: Record<string, { bg: string; text: string }> = {
  emergence: { bg: 'bg-green-900/40', text: 'text-green-400' },
  diffusion: { bg: 'bg-blue-900/40', text: 'text-blue-400' },
  consensus: { bg: 'bg-amber-900/40', text: 'text-amber-400' },
  monetization: { bg: 'bg-purple-900/40', text: 'text-purple-400' },
  decay: { bg: 'bg-red-900/40', text: 'text-red-400' },
}

interface Props {
  regime: string
  score?: number | null
  direction?: string
  watchStatus?: string | null
}

export default function RegimeBadge({ regime, score, direction, watchStatus }: Props) {
  const style = REGIME_STYLES[regime] || { bg: 'bg-card-hover', text: 'text-text-muted' }

  const arrow = direction === 'upgrading' ? ' \u25B2' :
    direction === 'downgrading' ? ' \u25BC' : ''
  const arrowColor = direction === 'upgrading' ? 'text-green-400' :
    direction === 'downgrading' ? 'text-red-400' : ''

  const isOnWatch = watchStatus === 'upgrade_watch' || watchStatus === 'downgrade_watch'
  const watchDotColor = watchStatus === 'upgrade_watch' ? 'bg-amber-400' : 'bg-red-400'

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text}`}>
      {isOnWatch && (
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${watchDotColor} animate-pulse`} />
      )}
      {regime}
      {score != null && (
        <span className="opacity-70 ml-0.5">{Math.round(score)}</span>
      )}
      {arrow && (
        <span className={`text-[10px] ${arrowColor}`}>{arrow}</span>
      )}
    </span>
  )
}
