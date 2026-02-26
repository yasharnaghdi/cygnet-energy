import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Zone = 'DE' | 'FR' | 'ES' | 'IT' | 'NL' | 'BE' | 'AT' | 'CH' | 'DK' | 'PL'
export type Persona = 'trader' | 'operator' | 'ev_owner' | 'policymaker'

interface SessionState {
  zone: Zone
  dateRange: [string, string]
  persona: Persona
  scenario: string
  sessionId: string | null

  setZone: (z: Zone) => void
  setDateRange: (r: [string, string]) => void
  setPersona: (p: Persona) => void
  setScenario: (s: string) => void
  setSessionId: (id: string | null) => void
}

const ZONES: Zone[] = ['DE', 'FR', 'ES', 'IT', 'NL', 'BE', 'AT', 'CH', 'DK', 'PL']
const PERSONAS: Persona[] = ['trader', 'operator', 'ev_owner', 'policymaker']
const defaultEnd = new Date().toISOString().slice(0, 10)
const defaultStart = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10)
const DEFAULT_ZONE: Zone = 'DE'
const DEFAULT_PERSONA: Persona = 'operator'

function normalizeZone(value: unknown): Zone {
  const zone = String(value ?? '').toUpperCase() as Zone
  return ZONES.includes(zone) ? zone : DEFAULT_ZONE
}

function normalizePersona(value: unknown): Persona {
  const raw = String(value ?? '').toLowerCase()
  if (raw === 'analyst' || raw === 'fleet_manager' || raw === 'grid_operator') {
    return 'operator'
  }
  if (raw === 'policy_analyst') {
    return 'policymaker'
  }
  if (PERSONAS.includes(raw as Persona)) {
    return raw as Persona
  }
  return DEFAULT_PERSONA
}

function normalizeDateRange(value: unknown): [string, string] {
  if (!Array.isArray(value) || value.length !== 2) {
    return [defaultStart, defaultEnd]
  }
  const [startRaw, endRaw] = value
  const start = String(startRaw ?? '')
  const end = String(endRaw ?? '')
  const isoPattern = /^\d{4}-\d{2}-\d{2}$/
  if (!isoPattern.test(start) || !isoPattern.test(end)) {
    return [defaultStart, defaultEnd]
  }
  return start <= end ? [start, end] : [end, start]
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      zone: DEFAULT_ZONE,
      dateRange: [defaultStart, defaultEnd],
      persona: DEFAULT_PERSONA,
      scenario: 'Base Case',
      sessionId: null,

      setZone: (zone) => set({ zone }),
      setDateRange: (dateRange) => set({ dateRange }),
      setPersona: (persona) => set({ persona }),
      setScenario: (scenario) => set({ scenario }),
      setSessionId: (sessionId) => set({ sessionId }),
    }),
    {
      name: 'cygnet-session',
      merge: (persistedState, currentState) => {
        const persisted = (persistedState ?? {}) as Partial<SessionState> & {
          zone?: unknown
          dateRange?: unknown
          persona?: unknown
          scenario?: unknown
          sessionId?: unknown
        }
        return {
          ...currentState,
          ...persisted,
          zone: normalizeZone(persisted.zone),
          dateRange: normalizeDateRange(persisted.dateRange),
          persona: normalizePersona(persisted.persona),
          scenario:
            typeof persisted.scenario === 'string' && persisted.scenario.trim().length > 0
              ? persisted.scenario
              : currentState.scenario,
          sessionId: typeof persisted.sessionId === 'string' ? persisted.sessionId : null,
        }
      },
    }
  )
)
