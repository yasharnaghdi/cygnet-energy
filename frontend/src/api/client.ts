import axios from 'axios'
import { notifications } from '@mantine/notifications'

const configuredBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim()
const baseURL = import.meta.env.DEV
  ? '/'
  : configuredBase && configuredBase.length > 0
    ? configuredBase
    : 'http://127.0.0.1:8001'

export const apiClient = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60_000,
})

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    const requestUrl = String(err.config?.url ?? '')
    const status = err.response?.status as number | undefined
    const suppressToastForGenerationFallback =
      requestUrl.includes('/generation/history') && (status === 404 || status === 500)
    if (suppressToastForGenerationFallback) {
      return Promise.reject(err)
    }

    const msg = err.response?.data?.detail
      ?? (err.message === 'Network Error'
        ? 'Network error: API unreachable. Confirm FastAPI is running on 127.0.0.1:8001.'
        : err.message)
      ?? 'Unknown error'
    notifications.show({
      title: 'API Error',
      message: String(msg),
      color: 'red',
    })
    return Promise.reject(err)
  }
)
