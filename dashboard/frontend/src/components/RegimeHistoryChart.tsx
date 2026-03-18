import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceArea } from 'recharts'
import type { RegimeHistoryPoint } from '../api/client'

interface Props {
  data: RegimeHistoryPoint[]
}

const REGIME_BANDS = [
  { y1: 0, y2: 20, color: '#22c55e', label: 'Emergence' },
  { y1: 20, y2: 40, color: '#3b82f6', label: 'Diffusion' },
  { y1: 40, y2: 60, color: '#f59e0b', label: 'Consensus' },
  { y1: 60, y2: 80, color: '#a855f7', label: 'Monetization' },
  { y1: 80, y2: 100, color: '#ef4444', label: 'Decay' },
]

export default function RegimeHistoryChart({ data }: Props) {
  if (!data.length) {
    return <div className="text-text-muted text-sm text-center py-8">No regime history available</div>
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        {/* Background color bands */}
        {REGIME_BANDS.map(band => (
          <ReferenceArea
            key={band.label}
            y1={band.y1}
            y2={band.y2}
            fill={band.color}
            fillOpacity={0.08}
          />
        ))}

        <XAxis
          dataKey="snapshot_date"
          tick={{ fill: '#6b7280', fontSize: 11 }}
          tickFormatter={(d: string) => d.slice(5)}
        />
        <YAxis
          domain={[0, 100]}
          ticks={[0, 20, 40, 60, 80, 100]}
          tick={{ fill: '#6b7280', fontSize: 11 }}
          width={35}
        />
        <Tooltip
          contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
          labelStyle={{ color: '#94a3b8' }}
          formatter={(value: number, _name: string) => [value.toFixed(1), 'Regime Score']}
          labelFormatter={(label: string) => `Date: ${label}`}
        />
        <Area
          type="monotone"
          dataKey="regime_score"
          stroke="#60a5fa"
          strokeWidth={2}
          fill="#60a5fa"
          fillOpacity={0.15}
          dot={false}
          activeDot={{ r: 4, fill: '#60a5fa' }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
