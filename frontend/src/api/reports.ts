import { apiClient } from './client'

export interface ReportRequest {
  persona: string
  zone?: string
  date_range?: [string, string]
  scenario?: string
  backend?: 'fallback' | 'openai' | 'ollama' | 'huggingface'
  model?: string
  save_history?: boolean
  session_context?: {
    zone?: string
    date_range?: [string, string]
    scenario?: string
    generation_context?: Record<string, unknown>
  }
}

export interface BackendEntry {
  type: string
  models?: string[]
  url?: string
  device?: string
}

export interface ReportBackendStatus {
  backend: string
  active_backend: string
  available_backends: BackendEntry[]
  available_backend_types: string[]
  openai_model?: string | null
  ollama_url?: string | null
  ollama_model?: string | null
  hf_model?: string | null
  hf_device?: string | null
}

export interface ReportSummary {
  report_id: string
  session_id?: string
  persona: string
  zone: string
  generated_at: string
  is_favorite: boolean
}

export interface ReportDetail extends ReportSummary {
  narrative: string
  data_summary: Record<string, unknown>
  backend: string
  session_id?: string
}

export interface ReportHistoryResponse {
  reports: ReportSummary[]
  total: number
  limit: number
  offset: number
}

export const reportsApi = {
  generate: (req: ReportRequest): Promise<ReportDetail> =>
    apiClient
      .post('/api/reports/generate', req, {
        timeout: req.backend === 'openai' ? 60_000 : 200_000,
      })
      .then((r) => r.data),

  list: (): Promise<ReportHistoryResponse> => apiClient.get('/api/reports/history').then((r) => r.data),

  get: (id: string): Promise<ReportDetail> => apiClient.get(`/api/reports/history/${id}`).then((r) => r.data),

  backendStatus: (): Promise<ReportBackendStatus> =>
    apiClient.get('/api/reports/backend-status').then((r) => r.data),

  toggleFavorite: (id: string, value: boolean) =>
    apiClient.patch(`/api/reports/history/${id}`, { is_favorite: value }),

  delete: (id: string) => apiClient.delete(`/api/reports/history/${id}`),
}
