import { useQuery } from '@tanstack/react-query'
import { ingestApi } from '../api/ingest'

export function useIngestStatus() {
  return useQuery({
    queryKey: ['ingest-status'],
    queryFn: ingestApi.status,
    refetchInterval: 1000 * 30,
  })
}
