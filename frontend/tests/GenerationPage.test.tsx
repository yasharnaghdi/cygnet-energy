import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, test } from 'vitest'
import { GenerationPage } from '../src/pages/GenerationPage'
import { server } from './msw/server'
import { useSessionStore } from '../src/store/sessionStore'

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <MemoryRouter initialEntries={['/generation']}>
      <QueryClientProvider client={queryClient}>
        <MantineProvider>
          <GenerationPage />
        </MantineProvider>
      </QueryClientProvider>
    </MemoryRouter>
  )
}

describe('GenerationPage', () => {
  beforeEach(() => {
    useSessionStore.setState({
      zone: 'FR',
      dateRange: ['2025-11-01', '2025-11-30'],
      persona: 'operator',
      scenario: 'Base Case',
      sessionId: null,
    })
  })

  test('renders generation analytics summary from API data', async () => {
    server.use(
      http.get('/generation/history', () =>
        HttpResponse.json([
          { time: '2025-11-30T22:00:00Z', psr_type: 'B19', actual_generation_mw: 900 },
          { time: '2025-11-30T23:00:00Z', psr_type: 'B19', actual_generation_mw: 1000 },
          { time: '2025-11-30T23:00:00Z', psr_type: 'B18', actual_generation_mw: 500 },
          { time: '2025-11-30T23:00:00Z', psr_type: 'B04', actual_generation_mw: 750 },
        ])
      )
    )

    renderPage()

    expect(await screen.findByText('Generation Analytics - FR')).toBeInTheDocument()
    expect(screen.getByText('2025-11-01 to 2025-11-30')).toBeInTheDocument()
    expect(screen.getByText('Generation Mix (MW)')).toBeInTheDocument()
    expect(screen.getByText('Renewable Share')).toBeInTheDocument()
    expect(screen.getByText('66.7%')).toBeInTheDocument()
    expect(screen.getByText('Total generation: 2,250 MW')).toBeInTheDocument()
  })
})
