import { Stack, Text } from '@mantine/core'
import { ReportPanel } from '../components/reports/ReportPanel'

export function AIInsightsPage() {
  return (
    <Stack gap="md">
      <Text fw={700} size="xl">
        AI Insights
      </Text>
      <ReportPanel />
    </Stack>
  )
}
