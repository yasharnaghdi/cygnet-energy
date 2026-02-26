import { ActionIcon, Burger, Group, Text, useMantineColorScheme } from '@mantine/core'
import { IconBolt, IconMoon, IconSun } from '@tabler/icons-react'

interface TopBarProps {
  opened: boolean
  onToggleNav: () => void
}

export function TopBar({ opened, onToggleNav }: TopBarProps) {
  const { colorScheme, setColorScheme } = useMantineColorScheme()

  return (
    <Group h="100%" px="md" justify="space-between">
      <Group>
        <Burger opened={opened} onClick={onToggleNav} hiddenFrom="sm" size="sm" />
        <Group gap={6}>
          <IconBolt size={18} color="var(--mantine-color-teal-5)" />
          <Text fw={700} size="lg" c="teal">
            Cygnet
          </Text>
          <Text size="xs" c="dimmed">
            Quantum Analytics
          </Text>
        </Group>
      </Group>

      <ActionIcon
        variant="subtle"
        onClick={() => setColorScheme(colorScheme === 'dark' ? 'light' : 'dark')}
        aria-label="Toggle color scheme"
      >
        {colorScheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
      </ActionIcon>
    </Group>
  )
}
