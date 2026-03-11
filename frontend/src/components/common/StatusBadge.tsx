import { Badge } from '@mantine/core'

interface StatusBadgeProps {
  status: 'ok' | 'no_data' | 'error' | string
}

const COLOR: Record<string, string> = {
  ok: 'teal',
  no_data: 'yellow',
  error: 'red',
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <Badge color={COLOR[status] ?? 'gray'} variant="light">
      {status}
    </Badge>
  )
}
