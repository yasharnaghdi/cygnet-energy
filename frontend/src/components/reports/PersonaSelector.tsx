import { SegmentedControl, Stack, Text } from '@mantine/core'
import { Persona, useSessionStore } from '../../store/sessionStore'

const OPTIONS: { value: Persona; label: string }[] = [
  { value: 'trader', label: 'Trader' },
  { value: 'operator', label: 'Operator' },
  { value: 'ev_owner', label: 'EV Owner' },
  { value: 'policymaker', label: 'Policy' },
]

export function PersonaSelector() {
  const { persona, setPersona } = useSessionStore()

  return (
    <Stack gap={4}>
      <Text size="xs" fw={600} c="dimmed">
        Report persona
      </Text>
      <SegmentedControl size="xs" data={OPTIONS} value={persona} onChange={(v) => setPersona(v as Persona)} />
    </Stack>
  )
}
