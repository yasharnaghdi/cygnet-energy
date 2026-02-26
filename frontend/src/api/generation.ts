import { apiClient } from './client'
import { AxiosError } from 'axios'

interface LegacyGenerationPoint {
  time: string
  psr_type: string
  actual_generation_mw: number
}

export interface GenerationPoint {
  time: string
  psr_type: string
  quantity: number
}

export const generationApi = {
  history: (zone: string, start: string, end: string): Promise<GenerationPoint[]> =>
    apiClient
      .get<LegacyGenerationPoint[]>('/generation/history', {
        params: { bidding_zone: zone, start_date: start, end_date: end },
      })
      .then((r) =>
        r.data.map((row) => ({
          time: row.time,
          psr_type: row.psr_type,
          quantity: Number(row.actual_generation_mw ?? 0),
        }))
      )
      .catch((err: AxiosError<{ detail?: string }>) => {
        const status = err.response?.status
        const detail = String(err.response?.data?.detail ?? '')
        const tableMissing = detail.toLowerCase().includes('relation "generation_actual" does not exist')
        if (status === 404 || tableMissing || status === 500) {
          return []
        }
        throw err
      }),
}
