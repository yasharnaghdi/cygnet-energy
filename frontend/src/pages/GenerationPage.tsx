import { Alert, Center, Loader, SimpleGrid, Stack, Text } from '@mantine/core'
import { GenerationChart } from '../components/charts/GenerationChart'
import { RenewableGauge } from '../components/charts/RenewableGauge'
import { useGeneration } from '../hooks/useGeneration'
import { summarizeGenerationWindow } from '../features/generation/summary'
import { useSessionStore } from '../store/sessionStore'

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

  const summary = summarizeGenerationWindow(data ?? [])

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
