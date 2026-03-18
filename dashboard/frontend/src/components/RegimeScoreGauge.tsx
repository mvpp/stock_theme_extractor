import { useMemo } from 'react'

interface Props {
  score: number         // 0-100
  label: string         // emergence/diffusion/consensus/monetization/decay
  direction: string     // upgrading/stable/downgrading
  watchStatus?: string | null  // upgrade_watch/downgrade_watch/null
}

const SEGMENTS = [
  { label: 'E', color: '#22c55e', end: 20 },
  { label: 'D', color: '#3b82f6', end: 40 },
  { label: 'C', color: '#f59e0b', end: 60 },
  { label: 'M', color: '#a855f7', end: 80 },
  { label: 'X', color: '#ef4444', end: 100 },
]

const REGIME_FULL: Record<string, string> = {
  emergence: 'EMERGENCE',
  diffusion: 'DIFFUSION',
  consensus: 'CONSENSUS',
  monetization: 'MONETIZATION',
  decay: 'DECAY',
}

export default function RegimeScoreGauge({ score, label, direction, watchStatus }: Props) {
  const clampedScore = Math.max(0, Math.min(100, score))

  // Needle angle: 0 score = -90deg (left), 100 score = +90deg (right)
  const needleAngle = useMemo(() => {
    return -90 + (clampedScore / 100) * 180
  }, [clampedScore])

  const cx = 150, cy = 140
  const outerR = 110, innerR = 80
  const tickR = outerR + 8

  // Arc path for each segment
  function arcPath(startPct: number, endPct: number, r: number): string {
    const startAngle = Math.PI + (startPct / 100) * Math.PI
    const endAngle = Math.PI + (endPct / 100) * Math.PI
    const x1 = cx + r * Math.cos(startAngle)
    const y1 = cy + r * Math.sin(startAngle)
    const x2 = cx + r * Math.cos(endAngle)
    const y2 = cy + r * Math.sin(endAngle)
    return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`
  }

  // Tick position
  function tickPos(pct: number) {
    const angle = Math.PI + (pct / 100) * Math.PI
    return {
      x1: cx + (outerR - 2) * Math.cos(angle),
      y1: cy + (outerR - 2) * Math.sin(angle),
      x2: cx + (outerR + 5) * Math.cos(angle),
      y2: cy + (outerR + 5) * Math.sin(angle),
      tx: cx + tickR * Math.cos(angle),
      ty: cy + tickR * Math.sin(angle),
    }
  }

  const directionArrow = direction === 'upgrading' ? '▲' :
    direction === 'downgrading' ? '▼' : '—'
  const directionColor = direction === 'upgrading' ? '#22c55e' :
    direction === 'downgrading' ? '#ef4444' : '#6b7280'

  const isOnWatch = watchStatus === 'upgrade_watch' || watchStatus === 'downgrade_watch'
  const watchColor = watchStatus === 'upgrade_watch' ? '#f59e0b' : '#ef4444'

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 300 185" width="300" height="185" className="overflow-visible">
        {/* Arc segments */}
        {SEGMENTS.map((seg, i) => {
          const startPct = i === 0 ? 0 : SEGMENTS[i - 1].end
          return (
            <path
              key={seg.label}
              d={arcPath(startPct, seg.end, outerR)}
              fill="none"
              stroke={seg.color}
              strokeWidth={outerR - innerR}
              strokeLinecap="butt"
              opacity={label === Object.keys(REGIME_FULL)[i] ? 1 : 0.35}
            />
          )
        })}

        {/* Inner dark circle to create donut */}
        <circle cx={cx} cy={cy} r={innerR - 1} fill="#1a1a2e" />

        {/* Tick marks at boundaries */}
        {[0, 20, 40, 60, 80, 100].map(pct => {
          const t = tickPos(pct)
          return (
            <g key={pct}>
              <line x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2}
                stroke="#9ca3af" strokeWidth={1.5} />
              <text x={t.tx} y={t.ty} fill="#9ca3af" fontSize="9"
                textAnchor="middle" dominantBaseline="middle">
                {pct}
              </text>
            </g>
          )
        })}

        {/* Segment labels */}
        {SEGMENTS.map((seg, i) => {
          const midPct = i === 0 ? seg.end / 2 : (SEGMENTS[i - 1].end + seg.end) / 2
          const angle = Math.PI + (midPct / 100) * Math.PI
          const lx = cx + (outerR - 15) * Math.cos(angle)
          const ly = cy + (outerR - 15) * Math.sin(angle)
          return (
            <text key={`label-${seg.label}`} x={lx} y={ly}
              fill="white" fontSize="10" fontWeight="bold"
              textAnchor="middle" dominantBaseline="middle"
              opacity={0.7}>
              {seg.label}
            </text>
          )
        })}

        {/* Needle */}
        <g transform={`rotate(${needleAngle} ${cx} ${cy})`}>
          <polygon
            points={`${cx},${cy - 75} ${cx - 4},${cy} ${cx + 4},${cy}`}
            fill={isOnWatch ? watchColor : '#e2e8f0'}
            className={isOnWatch ? 'animate-pulse' : ''}
          />
          {/* Pivot dot */}
          <circle cx={cx} cy={cy} r={6} fill="#e2e8f0" />
          <circle cx={cx} cy={cy} r={3} fill="#1a1a2e" />
        </g>

        {/* Score text */}
        <text x={cx} y={cy + 30} fill="white" fontSize="28" fontWeight="bold"
          textAnchor="middle">
          {Math.round(clampedScore)}
        </text>

        {/* Direction arrow */}
        <text x={cx + 28} y={cy + 28} fill={directionColor} fontSize="14"
          textAnchor="middle">
          {directionArrow}
        </text>

        {/* Regime label */}
        <text x={cx} y={cy + 50} fill="#9ca3af" fontSize="11"
          textAnchor="middle" letterSpacing="2">
          {REGIME_FULL[label] || label.toUpperCase()}
        </text>

        {/* Watch status */}
        {isOnWatch && (
          <text x={cx} y={cy + 66} fill={watchColor} fontSize="10"
            textAnchor="middle" className="animate-pulse">
            {watchStatus === 'upgrade_watch' ? '⬆ Upgrade Watch' : '⬇ Downgrade Watch'}
          </text>
        )}
      </svg>
    </div>
  )
}
