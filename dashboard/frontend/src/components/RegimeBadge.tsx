const REGIME_STYLES: Record<string, { bg: string; text: string }> = {
  emergence: { bg: 'bg-green-900/40', text: 'text-green-400' },
  diffusion: { bg: 'bg-blue-900/40', text: 'text-blue-400' },
  consensus: { bg: 'bg-amber-900/40', text: 'text-amber-400' },
  monetization: { bg: 'bg-purple-900/40', text: 'text-purple-400' },
  decay: { bg: 'bg-red-900/40', text: 'text-red-400' },
}

export default function RegimeBadge({ regime }: { regime: string }) {
  const style = REGIME_STYLES[regime] || { bg: 'bg-card-hover', text: 'text-text-muted' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text}`}>
      {regime}
    </span>
  )
}
