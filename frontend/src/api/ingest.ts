import { apiClient } from './client'

export interface IngestStatusZone {
  zone: string
  rows: number
  latest: string | null
}

export interface IngestStatus {
  zones: IngestStatusZone[]
}

export interface IngestRequest {
  zone: string
  start: string
  end: string
  overwrite?: boolean
}

export interface IngestResponse {
  status: string
  zone: string
  rows_inserted: number
  rows_skipped: number
  start: string
  end: string
  errors: string[]
}

function toIsoBoundary(value: string, isEnd: boolean): string {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return `${value}T${isEnd ? '23:59:59' : '00:00:00'}Z`
  }
  return value
}

export const ingestApi = {
  status: (): Promise<IngestStatus> => apiClient.get('/api/ingest/status').then((r) => r.data),

  ingest: (req: IngestRequest): Promise<IngestResponse> =>
    apiClient
      .post('/api/ingest/generation', {
        ...req,
        start: toIsoBoundary(req.start, false),
        end: toIsoBoundary(req.end, true),
      })
      .then((r) => r.data),
}
