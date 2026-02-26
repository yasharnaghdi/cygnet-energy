import { Divider, NavLink, Stack, Text } from '@mantine/core'
import { IconBrain, IconBolt, IconDatabaseImport } from '@tabler/icons-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { DateRangePicker } from '../common/DateRangePicker'
import { ZoneSelect } from '../common/ZoneSelect'

const NAV = [
  { label: 'Generation', path: '/generation', icon: IconBolt },
  { label: 'AI Insights', path: '/insights', icon: IconBrain },
  { label: 'Ingestion', path: '/ingest', icon: IconDatabaseImport },
]

export function Sidebar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  return (
    <Stack gap="xs">
      <Text size="xs" fw={600} c="dimmed" tt="uppercase">
        Context
      </Text>
      <ZoneSelect />
      <DateRangePicker />
      <Divider my="sm" />
      <Text size="xs" fw={600} c="dimmed" tt="uppercase">
        Navigation
      </Text>
      {NAV.map((item) => {
        const Icon = item.icon
        return (
          <NavLink
            key={item.path}
            label={item.label}
            leftSection={<Icon size={16} />}
            active={pathname === item.path}
            onClick={() => navigate(item.path)}
          />
        )
      })}
    </Stack>
  )
}
