interface TrendArrowProps {
  value: number  // positive = heating, negative = cooling, 0 = stable
  label?: string
}

export default function TrendArrow({ value, label }: TrendArrowProps) {
  let arrow: string
  let color: string

  if (value > 0.5) {
    arrow = '↑'
    color = 'text-positive'
  } else if (value > 0) {
    arrow = '↗'
    color = 'text-green-300'
  } else if (value < -0.5) {
    arrow = '↓'
    color = 'text-negative'
  } else if (value < 0) {
    arrow = '↘'
    color = 'text-red-300'
  } else {
    arrow = '→'
    color = 'text-text-muted'
  }

  return (
    <span className={`${color} font-medium`}>
      {arrow} {label && <span className="text-xs">{label}</span>}
    </span>
  )
}
