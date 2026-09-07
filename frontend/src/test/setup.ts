import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach } from 'vitest'
import { cleanup } from '@testing-library/react'

/**
 * Provide a working `localStorage` for the test environment.
 *
 * Two things conspire to leave one missing here: Node 20+ defines its own
 * `localStorage` global that stays `undefined` unless the process was started
 * with --localstorage-file, and under that global jsdom does not install its
 * own on `window` either. The result is that a bare `localStorage` reference —
 * the form the app uses everywhere, and correct in a browser — is undefined.
 *
 * The app keeps its whole session in localStorage, so without this every auth
 * test would fail for an environment reason rather than a real one.
 */
function createMemoryStorage(): Storage {
  let entries = new Map<string, string>()

  return {
    get length() {
      return entries.size
    },
    key: (index: number) => [...entries.keys()][index] ?? null,
    getItem: (key: string) => entries.get(key) ?? null,
    setItem: (key: string, value: string) => {
      entries.set(key, String(value))
    },
    removeItem: (key: string) => {
      entries.delete(key)
    },
    clear: () => {
      entries = new Map()
    },
  } as Storage
}

if (!globalThis.localStorage) {
  const storage = createMemoryStorage()
  for (const target of [globalThis, window]) {
    Object.defineProperty(target, 'localStorage', {
      value: storage,
      configurable: true,
      writable: true,
    })
  }
}

// Component tests share one jsdom per file, and this app keeps its session in
// localStorage — without clearing it a signed-in test would leak into the next
// one and quietly mask a broken auth path.
beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  cleanup()
})
