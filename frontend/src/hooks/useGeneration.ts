import { useQuery } from '@tanstack/react-query'
import { generationApi } from '../api/generation'
import { useSessionStore } from '../store/sessionStore'

export function useGeneration() {
  const { zone, dateRange } = useSessionStore()
  return useQuery({
    queryKey: ['generation', zone, dateRange],
    queryFn: async () => {
      try {
        return await generationApi.history(zone, dateRange[0], dateRange[1])
      } catch {
        return []
      }
    },
    enabled: Boolean(zone && dateRange[0]),
    retry: false,
  })
}
