import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import { server } from '../../tests/msw/server'

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function createStorageMock(): Storage {
  let store = new Map<string, string>()
  return {
    get length() {
      return store.size
    },
    clear() {
      store = new Map<string, string>()
    },
    getItem(key: string) {
      return store.get(key) ?? null
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null
    },
    removeItem(key: string) {
      store.delete(key)
    },
    setItem(key: string, value: string) {
      store.set(key, value)
    },
  }
}

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
  vi.stubGlobal('ResizeObserver', ResizeObserverMock)
  const storage = createStorageMock()
  Object.defineProperty(window, 'localStorage', {
    writable: true,
    value: storage,
  })
  Object.defineProperty(globalThis, 'localStorage', {
    writable: true,
    value: storage,
  })
  if (!window.matchMedia) {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
    })
  }
})

afterEach(() => {
  server.resetHandlers()
  cleanup()
  localStorage.clear()
})

afterAll(() => {
  server.close()
})
