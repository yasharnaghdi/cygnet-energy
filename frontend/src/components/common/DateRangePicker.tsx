import { Button, Group, Stack, Text } from '@mantine/core'
import { DateInput } from '@mantine/dates'
import dayjs from 'dayjs'
import { useSessionStore } from '../../store/sessionStore'

const PRESETS: { label: string; days: number }[] = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
]

function toDateOrNull(value: string): Date | null {
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.toDate() : null
}

export function DateRangePicker() {
  const { dateRange, setDateRange } = useSessionStore()
  const [start, end] = dateRange
  const endOfToday = dayjs().endOf('day').toDate()

  function setStartDate(next: Date) {
    const nextIso = dayjs(next).format('YYYY-MM-DD')
    if (dayjs(nextIso).isAfter(end, 'day')) {
      setDateRange([nextIso, nextIso])
      return
    }
    setDateRange([nextIso, end])
  }

  function setEndDate(next: Date) {
    const nextIso = dayjs(next).format('YYYY-MM-DD')
    if (dayjs(nextIso).isBefore(start, 'day')) {
      setDateRange([nextIso, nextIso])
      return
    }
    setDateRange([start, nextIso])
  }

  function applyPreset(days: number) {
    const presetEnd = dayjs().format('YYYY-MM-DD')
    const presetStart = dayjs().subtract(days, 'day').format('YYYY-MM-DD')
    setDateRange([presetStart, presetEnd])
  }

  return (
    <Stack gap={6}>
      <Text size="xs" fw={600} c="dimmed">
        Date range
      </Text>
      <DateInput
        label="Start"
        size="sm"
        value={toDateOrNull(start)}
        valueFormat="YYYY-MM-DD"
        maxDate={toDateOrNull(end) ?? endOfToday}
        onChange={(value) => {
          if (value) {
            setStartDate(value)
          }
        }}
      />
      <DateInput
        label="End"
        size="sm"
        value={toDateOrNull(end)}
        valueFormat="YYYY-MM-DD"
        minDate={toDateOrNull(start) ?? undefined}
        maxDate={endOfToday}
        onChange={(value) => {
          if (value) {
            setEndDate(value)
          }
        }}
      />
      <Group gap={4}>
        {PRESETS.map((preset) => (
          <Button
            key={preset.label}
            size="compact-xs"
            variant="light"
            color="gray"
            onClick={() => applyPreset(preset.days)}
          >
            {preset.label}
          </Button>
        ))}
      </Group>
      <Text size="xs" c="dimmed">
        Selected: {start} to {end}
      </Text>
    </Stack>
  )
}
