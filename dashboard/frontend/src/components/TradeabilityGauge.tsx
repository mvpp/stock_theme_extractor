import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts'

interface TradeabilityGaugeProps {
  components: {
    relevance: number
    uniqueness: number
    recency: number
    corroboration: number
    narrative_intensity: number
    taxonomy_depth: number
  }
  score: number
}

const LABELS: Record<string, string> = {
  relevance: 'Relevance',
  uniqueness: 'Uniqueness',
  recency: 'Recency',
  corroboration: 'Corroboration',
  narrative_intensity: 'Narrative',
  taxonomy_depth: 'Specificity',
}

export default function TradeabilityGauge({ components, score }: TradeabilityGaugeProps) {
  const data = Object.entries(components).map(([key, value]) => ({
    dimension: LABELS[key] || key,
    value: Math.round(value * 100),
    fullMark: 100,
  }))

  return (
    <div className="bg-card rounded-lg border border-border p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-text-primary">Tradeability Score</h3>
        <span className="text-2xl font-bold text-accent">
          {Math.round(score * 100)}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <RadarChart data={data}>
          <PolarGrid stroke="#262626" />
          <PolarAngleAxis dataKey="dimension" tick={{ fill: '#a3a3a3', fontSize: 11 }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            name="Score"
            dataKey="value"
            stroke="#0693e3"
            fill="#0693e3"
            fillOpacity={0.2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
