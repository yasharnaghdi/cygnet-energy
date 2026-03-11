import { Badge, Button, Group, Paper, Stack, Table, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ingestApi } from '../api/ingest'
import { useIngestStatus } from '../hooks/useIngestStatus'
import { useSessionStore } from '../store/sessionStore'

export function IngestionPage() {
  const { zone, dateRange } = useSessionStore()
  const { data: status } = useIngestStatus()
  const queryClient = useQueryClient()
  const [start, end] = dateRange

  const ingest = useMutation({
    mutationFn: () => ingestApi.ingest({ zone, start, end }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['ingest-status'] })
      queryClient.invalidateQueries({ queryKey: ['generation'] })
      notifications.show({
        title: `Ingested ${result.zone}`,
        message: `${result.rows_inserted} rows inserted, ${result.rows_skipped} skipped`,
        color: 'teal',
      })
    },
  })

  return (
    <Stack gap="md">
      <Text fw={700} size="xl">
        Data Ingestion
      </Text>

      <Paper p="md" radius="md" withBorder>
        <Stack gap="sm">
          <Text fw={600} size="sm">
            Fetch from ENTSO-E
          </Text>
          <Text size="sm" c="dimmed">
            Uses sidebar context for zone and dates.
          </Text>
          <Group>
            <Badge variant="outline" color="teal">
              {zone}
            </Badge>
            <Badge variant="outline" color="gray">
              {start} to {end}
            </Badge>
            <Button onClick={() => ingest.mutate()} loading={ingest.isPending} color="teal" disabled={start > end}>
              Fetch
            </Button>
          </Group>
        </Stack>
      </Paper>

      <Paper p="md" radius="md" withBorder>
        <Text fw={600} size="sm" mb="sm">
          DB Status by Zone
        </Text>
        <Table>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Zone</Table.Th>
              <Table.Th>Rows</Table.Th>
              <Table.Th>Latest timestamp</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {(status?.zones ?? []).map((item) => (
              <Table.Tr key={item.zone}>
                <Table.Td>
                  <Badge variant="light">{item.zone}</Badge>
                </Table.Td>
                <Table.Td>{item.rows.toLocaleString()}</Table.Td>
                <Table.Td>{item.latest?.slice(0, 16) ?? '-'}</Table.Td>
              </Table.Tr>
            ))}
            {(!status?.zones || status.zones.length === 0) && (
              <Table.Tr>
                <Table.Td colSpan={3}>
                  <Text c="dimmed" size="sm">
                    No data ingested yet.
                  </Text>
                </Table.Td>
              </Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      </Paper>
    </Stack>
  )
}
