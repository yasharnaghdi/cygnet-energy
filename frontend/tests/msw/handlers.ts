import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/generation/history', () => HttpResponse.json([])),
]
