import { ActionIcon, Drawer, Group, Loader, Paper, Stack, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconStar, IconStarFilled, IconTrash } from '@tabler/icons-react'
import { useQueryClient } from '@tanstack/react-query'
import { reportsApi } from '../../api/reports'
import { useReportHistory } from '../../hooks/useReports'

interface Props {
  opened: boolean
  onClose: () => void
}

export function ReportHistoryDrawer({ opened, onClose }: Props) {
  const { data, isLoading } = useReportHistory()
  const queryClient = useQueryClient()
  const reports = data?.reports ?? []

  async function toggleFav(id: string, current: boolean) {
    await reportsApi.toggleFavorite(id, !current)
    await queryClient.invalidateQueries({ queryKey: ['report-history'] })
  }

  async function handleDelete(id: string) {
    await reportsApi.delete(id)
    await queryClient.invalidateQueries({ queryKey: ['report-history'] })
    notifications.show({ message: 'Report deleted', color: 'red' })
  }

  return (
    <Drawer opened={opened} onClose={onClose} title="Report History" position="right" size="md">
      {isLoading && <Loader />}

      <Stack gap="sm">
        {reports.map((r) => (
          <Paper key={r.report_id} p="sm" radius="md" withBorder>
            <Group justify="space-between" wrap="nowrap">
              <Stack gap={2}>
                <Text size="sm" fw={600}>
                  {r.persona} - {r.zone}
                </Text>
                <Text size="xs" c="dimmed">
                  {r.generated_at.slice(0, 16)}
                </Text>
              </Stack>
              <Group gap="xs">
                <ActionIcon
                  variant="subtle"
                  color={r.is_favorite ? 'yellow' : 'gray'}
                  onClick={() => toggleFav(r.report_id, r.is_favorite)}
                  aria-label="Toggle favorite"
                >
                  {r.is_favorite ? <IconStarFilled size={16} /> : <IconStar size={16} />}
                </ActionIcon>
                <ActionIcon
                  variant="subtle"
                  color="red"
                  onClick={() => handleDelete(r.report_id)}
                  aria-label="Delete report"
                >
                  <IconTrash size={16} />
                </ActionIcon>
              </Group>
            </Group>
          </Paper>
        ))}

        {reports.length === 0 && !isLoading && (
          <Text c="dimmed" size="sm">
            No reports yet.
          </Text>
        )}
      </Stack>
    </Drawer>
  )
}
