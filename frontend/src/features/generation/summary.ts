import { GenerationPoint } from '../../api/generation'

const RENEWABLE_CODES = new Set(['B01', 'B09', 'B10', 'B11', 'B12', 'B15', 'B16', 'B18', 'B19', 'B20'])

export interface GenerationSummary {
  renewablePct: number
  totalMw: number
}

export function summarizeLatestGeneration(points: GenerationPoint[]): GenerationSummary {
  if (!points.length) {
    return { renewablePct: 0, totalMw: 0 }
  }

  const latest = points.reduce((max, point) => (point.time > max ? point.time : max), points[0].time)
  const latestRows = points.filter((point) => point.time === latest)

  const totalMw = latestRows.reduce((sum, point) => sum + point.quantity, 0)
  const renewableMw = latestRows
    .filter((point) => RENEWABLE_CODES.has(point.psr_type))
    .reduce((sum, point) => sum + point.quantity, 0)

  return {
    totalMw,
    renewablePct: totalMw > 0 ? (renewableMw / totalMw) * 100 : 0,
  }
}
