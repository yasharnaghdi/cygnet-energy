import { Badge, Button, Group, Loader, Paper, Select, Stack, Text, TextInput, Textarea } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconSparkles } from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { useGeneration } from '../../hooks/useGeneration'
import { useGenerateReport, useReportBackendStatus } from '../../hooks/useReports'
import { useSessionStore } from '../../store/sessionStore'
import { PersonaSelector } from './PersonaSelector'
import { ReportHistoryDrawer } from './ReportHistoryDrawer'

const RENEWABLE_PSR_TYPES = new Set(['B11', 'B16', 'B18', 'B19'])
const DEFAULT_BACKENDS = ['ollama', 'huggingface', 'openai', 'fallback'] as const
const BACKEND_LABEL: Record<string, string> = {
  ollama: 'Ollama (Local)',
  huggingface: 'Hugging Face (Local)',
  openai: 'OpenAI',
  fallback: 'Fallback Template',
}
const MODEL_PLACEHOLDER: Record<string, string> = {
  ollama: 'e.g. llama3.2:3b-instruct-q8_0',
  huggingface: 'e.g. mistralai/Mistral-7B-Instruct-v0.2',
  openai: 'e.g. gpt-4o-mini',
  fallback: '',
}

export function ReportPanel() {
  const { zone, dateRange, persona } = useSessionStore()
  const generation = useGeneration()
  const generate = useGenerateReport()
  const backendStatus = useReportBackendStatus()
  const [drawerOpen, { open, close }] = useDisclosure(false)
  const [narrative, setNarrative] = useState<string | null>(null)
  const [backendSelection, setBackendSelection] = useState<string>('ollama')
  const [modelSelection, setModelSelection] = useState<string>('')

  const backendMeta = useMemo(() => {
    const backendSet = new Set<string>(DEFAULT_BACKENDS)
    const modelsByBackend: Record<string, string[]> = {}

    function addModel(backend: string, model: string | null | undefined) {
      const normalizedBackend = backend.trim().toLowerCase()
      const normalizedModel = String(model ?? '').trim()
      if (!normalizedBackend || !normalizedModel) {
        return
      }
      const existing = modelsByBackend[normalizedBackend] ?? []
      if (!existing.includes(normalizedModel)) {
        modelsByBackend[normalizedBackend] = [...existing, normalizedModel]
      }
    }

    for (const entry of backendStatus.data?.available_backends ?? []) {
      const backendType = String(entry.type ?? '').trim().toLowerCase()
      if (!backendType) {
        continue
      }
      backendSet.add(backendType)
      for (const model of entry.models ?? []) {
        addModel(backendType, model)
      }
    }

    addModel('openai', backendStatus.data?.openai_model)
    addModel('ollama', backendStatus.data?.ollama_model)
    addModel('huggingface', backendStatus.data?.hf_model)

    const ordered = Array.from(backendSet).sort((a, b) => {
      const rankA = DEFAULT_BACKENDS.indexOf(a as (typeof DEFAULT_BACKENDS)[number])
      const rankB = DEFAULT_BACKENDS.indexOf(b as (typeof DEFAULT_BACKENDS)[number])
      const safeA = rankA === -1 ? DEFAULT_BACKENDS.length + 1 : rankA
      const safeB = rankB === -1 ? DEFAULT_BACKENDS.length + 1 : rankB
      return safeA - safeB || a.localeCompare(b)
    })

    return { orderedBackends: ordered, modelsByBackend }
  }, [
    backendStatus.data?.available_backends,
    backendStatus.data?.openai_model,
    backendStatus.data?.ollama_model,
    backendStatus.data?.hf_model,
  ])

  const backendOptions = useMemo(
    () =>
      backendMeta.orderedBackends.map((backend) => ({
        value: backend,
        label: BACKEND_LABEL[backend] ?? backend.toUpperCase(),
      })),
    [backendMeta.orderedBackends]
  )

  const selectedBackendModels = backendMeta.modelsByBackend[backendSelection] ?? []

  useEffect(() => {
    const active = String(backendStatus.data?.active_backend ?? '').trim().toLowerCase()
    if (active && backendMeta.orderedBackends.includes(active)) {
      setBackendSelection(active)
      return
    }
    if (!backendMeta.orderedBackends.includes(backendSelection)) {
      setBackendSelection(backendMeta.orderedBackends[0] ?? 'ollama')
    }
  }, [backendMeta.orderedBackends, backendStatus.data?.active_backend, backendSelection])

  useEffect(() => {
    if (backendSelection === 'fallback') {
      setModelSelection('')
      return
    }
    const firstSuggestedModel = selectedBackendModels[0] ?? ''
    setModelSelection((current) => current || firstSuggestedModel)
  }, [backendSelection, selectedBackendModels])

  async function handleGenerate() {
    const backend = backendSelection || undefined
    const model = backendSelection === 'fallback' ? undefined : modelSelection.trim() || undefined
    const generationRows = generation.data ?? []
    const totalGeneration = generationRows.reduce((sum, row) => sum + Number(row.quantity ?? 0), 0)
    const renewableGeneration = generationRows.reduce((sum, row) => {
      if (RENEWABLE_PSR_TYPES.has(row.psr_type)) {
        return sum + Number(row.quantity ?? 0)
      }
      return sum
    }, 0)
    const renewablePct = totalGeneration > 0 ? Number(((renewableGeneration / totalGeneration) * 100).toFixed(1)) : 0
    try {
      const result = await generate.mutateAsync({
        backend: backend as 'fallback' | 'openai' | 'ollama' | 'huggingface' | undefined,
        model,
        session_context: {
          generation_context: {
            zone,
            date_range: dateRange,
            rows: generationRows.length,
            renewable_pct: renewablePct,
            total_generation_mwh: Number(totalGeneration.toFixed(2)),
          },
        },
      })
      setNarrative(result.narrative)
    } catch {
      // Error display is handled by axios response interceptor.
    }
  }

  return (
    <Stack gap="md">
      <Paper p="md" radius="md" withBorder>
        <Stack gap="sm">
          <Group justify="space-between">
            <Text fw={600}>AI Insights</Text>
            <Group gap="xs">
              <Badge variant="outline" color="teal">
                {zone}
              </Badge>
              <Badge variant="outline" color="gray">
                {dateRange[0]} to {dateRange[1]}
              </Badge>
            </Group>
          </Group>

          <PersonaSelector />
          <Stack gap={4}>
            <Text size="xs" fw={600} c="dimmed">
              LLM backend
            </Text>
            <Select
              size="xs"
              data={backendOptions}
              value={backendSelection}
              onChange={(value) => {
                if (value) {
                  setBackendSelection(value)
                }
              }}
              rightSection={backendStatus.isLoading ? <Loader size="xs" /> : null}
            />
            {backendSelection !== 'fallback' && (
              <TextInput
                size="xs"
                label="Model override"
                placeholder={MODEL_PLACEHOLDER[backendSelection] ?? 'Model name'}
                value={modelSelection}
                onChange={(event) => setModelSelection(event.currentTarget.value)}
              />
            )}
            {selectedBackendModels.length > 0 && backendSelection !== 'fallback' && (
              <Text size="xs" c="dimmed">
                Suggested models: {selectedBackendModels.join(', ')}
              </Text>
            )}
            <Text size="xs" c="dimmed">
              Active backend: {backendStatus.data?.active_backend ?? 'unknown'}
            </Text>
          </Stack>

          <Group>
            <Button
              onClick={handleGenerate}
              loading={generate.isPending}
              color="teal"
              leftSection={generate.isPending ? <Loader size="xs" /> : <IconSparkles size={16} />}
            >
              Generate Report
            </Button>
            <Button variant="subtle" onClick={open}>
              History
            </Button>
          </Group>
        </Stack>
      </Paper>

      {narrative && (
        <Paper p="md" radius="md" withBorder>
          <Text size="xs" fw={600} c="dimmed" mb="xs">
            NARRATIVE - {persona.toUpperCase()}
          </Text>
          <Textarea
            value={narrative}
            readOnly
            autosize
            minRows={6}
            styles={{ input: { fontFamily: 'monospace', fontSize: 13 } }}
          />
        </Paper>
      )}

      <ReportHistoryDrawer opened={drawerOpen} onClose={close} />
    </Stack>
  )
}
