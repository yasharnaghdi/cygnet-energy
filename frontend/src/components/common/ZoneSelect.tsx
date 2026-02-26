import { Select } from '@mantine/core'
import { useSessionStore, Zone } from '../../store/sessionStore'

const ZONES: Zone[] = ['DE', 'FR', 'ES', 'IT', 'NL', 'BE', 'AT', 'CH', 'DK', 'PL']

export function ZoneSelect() {
  const { zone, setZone } = useSessionStore()

  return (
    <Select
      label="Zone"
      data={ZONES}
      value={zone}
      onChange={(value) => {
        if (value) {
          setZone(value as Zone)
        }
      }}
      size="sm"
      searchable
    />
  )
}
