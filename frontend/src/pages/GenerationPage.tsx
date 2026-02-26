import { Alert, Center, Loader, SimpleGrid, Stack, Text } from '@mantine/core'
import { GenerationPoint } from '../api/generation'
import { GenerationChart } from '../components/charts/GenerationChart'
import { RenewableGauge } from '../components/charts/RenewableGauge'
import { useGeneration } from '../hooks/useGeneration'
import { useSessionStore } from '../store/sessionStore'

const RENEWABLE_CODES = new Set(['B01', 'B09', 'B10', 'B11', 'B12', 'B15', 'B16', 'B18', 'B19', 'B20'])

function summarizeLatest(points: GenerationPoint[]): { renewablePct: number; totalMw: number } {
  if (!points.length) {
    return { renewablePct: 0, totalMw: 0 }
  }

  const latest = points.reduce((max, p) => (p.time > max ? p.time : max), points[0].time)
  const latestRows = points.filter((p) => p.time === latest)

  const totalMw = latestRows.reduce((sum, p) => sum + p.quantity, 0)
  const renewableMw = latestRows
    .filter((p) => RENEWABLE_CODES.has(p.psr_type))
    .reduce((sum, p) => sum + p.quantity, 0)

  return {
    totalMw,
    renewablePct: totalMw > 0 ? (renewableMw / totalMw) * 100 : 0,
  }
}

export function GenerationPage() {
  const { zone, dateRange } = useSessionStore()
  const { data, isLoading, isError } = useGeneration()

  if (isLoading) {
    return (
      <Center h={400}>
        <Loader color="teal" />
      </Center>
    )
  }

  const summary = summarizeLatest(data ?? [])

  return (
    <Stack gap="md">
      <Text fw={700} size="xl">
        Generation Analytics - {zone}
        <Text span size="sm" c="dimmed" ml="xs">
          {dateRange[0]} to {dateRange[1]}
        </Text>
      </Text>

      {data && data.length > 0 ? (
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
          <GenerationChart data={data} />
          <RenewableGauge renewablePct={summary.renewablePct} totalMw={summary.totalMw} />
        </SimpleGrid>
      ) : (
        <Alert color="yellow" title={isError ? 'Generation source unavailable' : 'No data'}>
          {isError
            ? `Generation source is unavailable for ${zone} right now. You can continue using Ingestion and AI Insights while this source is recovering.`
            : `No generation records for ${zone} in this range. Go to Ingestion to fetch data.`}
        </Alert>
      )}
    </Stack>
  )
}
