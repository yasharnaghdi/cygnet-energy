import { Paper, RingProgress, Stack, Text } from '@mantine/core'

interface RenewableGaugeProps {
  renewablePct: number
  totalMw: number
}

export function RenewableGauge({ renewablePct, totalMw }: RenewableGaugeProps) {
  const value = Number.isFinite(renewablePct) ? Math.max(0, Math.min(100, renewablePct)) : 0

  return (
    <Paper p="md" radius="md" withBorder>
      <Stack align="center" gap="xs">
        <Text size="sm" fw={600}>
          Renewable Share
        </Text>
        <RingProgress
          size={140}
          thickness={12}
          sections={[{ value, color: 'teal' }]}
          label={
            <Text ta="center" fw={700} size="lg">
              {value.toFixed(1)}%
            </Text>
          }
        />
        <Text size="xs" c="dimmed">
          Total generation: {Math.round(totalMw).toLocaleString()} MW
        </Text>
      </Stack>
    </Paper>
  )
}
