import { GenerationPoint } from '../../api/generation'
import { renewablePsrCodeSet } from './renewableCodes'

export interface GenerationSummary {
  renewablePct: number
  totalMw: number
}

export function summarizeGenerationWindow(points: GenerationPoint[]): GenerationSummary {
  if (!points.length) {
    return { renewablePct: 0, totalMw: 0 }
  }

  const totalMw = points.reduce((sum, point) => sum + point.quantity, 0)
  const renewableMw = points
    .filter((point) => renewablePsrCodeSet.has(point.psr_type))
    .reduce((sum, point) => sum + point.quantity, 0)

  return {
    totalMw,
    renewablePct: totalMw > 0 ? (renewableMw / totalMw) * 100 : 0,
  }
}
