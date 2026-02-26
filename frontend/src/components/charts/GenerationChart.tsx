import { Paper, Text } from '@mantine/core'
import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { GenerationPoint } from '../../api/generation'

type ChartRow = {
  time: string
  [key: string]: string | number
}

const PSR_COLORS: Record<string, string> = {
  B19: '#4fc3f7',
  B18: '#29b6f6',
  B16: '#ffca28',
  B11: '#26a69a',
  B14: '#7e57c2',
  B04: '#ef5350',
  B05: '#795548',
}

function pivot(data: GenerationPoint[]): ChartRow[] {
  const byTime: Record<string, ChartRow> = {}

  for (const point of data) {
    if (!byTime[point.time]) {
      byTime[point.time] = { time: point.time }
    }
    const prev = byTime[point.time][point.psr_type]
    const prevValue = typeof prev === 'number' ? prev : 0
    byTime[point.time][point.psr_type] = prevValue + point.quantity
  }

  return Object.values(byTime).sort((a, b) => a.time.localeCompare(b.time))
}

interface Props {
  data: GenerationPoint[]
}

export function GenerationChart({ data }: Props) {
  const chartData = useMemo(() => pivot(data), [data])
  const psrTypes = useMemo(() => [...new Set(data.map((d) => d.psr_type))], [data])

  return (
    <Paper p="md" radius="md" withBorder>
      <Text size="sm" fw={600} mb="xs">
        Generation Mix (MW)
      </Text>
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={chartData}>
          <XAxis dataKey="time" tickFormatter={(t) => String(t).slice(5, 16)} tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip
            formatter={(value: number | string, name: string) => {
              const numeric = typeof value === 'number' ? value : Number(value)
              return [`${numeric.toFixed(0)} MW`, name]
            }}
            labelFormatter={(label) => String(label).slice(0, 16)}
          />
          <Legend />
          {psrTypes.map((psr) => (
            <Area
              key={psr}
              type="monotone"
              dataKey={psr}
              stackId="1"
              stroke={PSR_COLORS[psr] ?? '#90a4ae'}
              fill={PSR_COLORS[psr] ?? '#90a4ae'}
              fillOpacity={0.7}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </Paper>
  )
}
