import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { notifications } from '@mantine/notifications'
import { ReportRequest, reportsApi } from '../api/reports'
import { useSessionStore } from '../store/sessionStore'

export function useReportHistory() {
  return useQuery({
    queryKey: ['report-history'],
    queryFn: reportsApi.list,
  })
}

export function useReportBackendStatus() {
  return useQuery({
    queryKey: ['report-backend-status'],
    queryFn: reportsApi.backendStatus,
    staleTime: 30_000,
  })
}

export function useGenerateReport() {
  const queryClient = useQueryClient()
  const { zone, dateRange, persona, scenario, setSessionId } = useSessionStore()

  return useMutation({
    mutationFn: (extra?: Partial<ReportRequest>) => {
      const mergedSessionContext = {
        zone,
        date_range: dateRange,
        scenario,
        generation_context: { zone, date_range: dateRange },
        ...(extra?.session_context ?? {}),
      }
      return reportsApi.generate({
        persona,
        zone,
        date_range: dateRange,
        scenario,
        save_history: true,
        ...extra,
        session_context: mergedSessionContext,
      })
    },
    onSuccess: (data) => {
      if (data.session_id || data.report_id) {
        setSessionId(data.session_id ?? data.report_id)
      }
      queryClient.invalidateQueries({ queryKey: ['report-history'] })
      notifications.show({
        title: 'Report ready',
        message: `${data.persona} - ${data.zone}`,
        color: 'teal',
      })
    },
  })
}
