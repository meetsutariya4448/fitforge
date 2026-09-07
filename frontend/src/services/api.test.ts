/**
 * Tests for the API client's refresh, retry and validation behaviour.
 *
 * These exercise the browser half of the atomic-rotation fix. The server now
 * lets exactly one caller redeem a refresh token, so a second tab that loses
 * the race gets a 401 — and the client must recognise that as "someone else
 * rotated" rather than "your session is over". Getting this wrong logs people
 * out for the crime of opening a second tab, which no server-side test can
 * catch.
 *
 * Requests are intercepted at the axios adapter, so the real interceptor chain
 * runs exactly as it does in the app.
 */

import { AxiosError, type AxiosAdapter, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import apiClient, {
  ApiError,
  getPRs,
  getWorkoutSessions,
  login,
  REFRESH_KEY,
  TOKEN_KEY,
  USER_KEY,
} from './api'

// ── Harness ───────────────────────────────────────────────────────────────────

interface Handler {
  (url: string, body: unknown): { status: number; data: unknown }
}

let handler: Handler
let requests: Array<{ url: string; auth: string | undefined }> = []

/** Install an adapter that routes every request through the current handler. */
const adapter: AxiosAdapter = async (config) => {
  const url = config.url ?? ''
  const body = config.data ? JSON.parse(config.data as string) : null
  requests.push({ url, auth: config.headers?.Authorization as string | undefined })

  const { status, data } = handler(url, body)
  const response = {
    data,
    status,
    statusText: String(status),
    headers: {},
    config,
  } as AxiosResponse

  if (status >= 400) {
    throw new AxiosError(`Request failed with status ${status}`, String(status), config, {}, response)
  }
  return response
}

const VALID_USER = { id: 1, email: 'a@b.com', name: 'Test User' }

function tokenResponse(suffix: string) {
  return {
    access_token: `access-${suffix}`,
    refresh_token: `refresh-${suffix}`,
    token_type: 'bearer',
    user: VALID_USER,
  }
}

function errorBody(code: string, message = 'nope') {
  return { error: { code, message } }
}

beforeEach(() => {
  apiClient.defaults.adapter = adapter
  requests = []
  handler = () => ({ status: 200, data: {} })

  // The interceptor navigates on an unrecoverable 401; jsdom cannot navigate,
  // so make the current path /auth, which the client already treats as "no
  // redirect needed".
  window.history.replaceState({}, '', '/auth')
})

// ── Error normalisation ───────────────────────────────────────────────────────

describe('toApiError', () => {
  it('reads the API error envelope', async () => {
    handler = () => ({ status: 409, data: errorBody('CONFLICT', 'Email already registered.') })

    const error = await login({ email: 'a@b.com', password: 'x' }).catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('CONFLICT')
    // The message must survive: users used to see only a generic fallback
    // because the client read a `detail` field the API never sends.
    expect(error.message).toBe('Email already registered.')
    expect(error.status).toBe(409)
  })

  it('reports a network failure distinctly from an HTTP error', async () => {
    handler = () => {
      throw new AxiosError('Network Error', 'ERR_NETWORK')
    }

    const error = await getPRs().catch((e) => e)

    expect(error.code).toBe('NETWORK_ERROR')
    expect(error.status).toBeNull()
    expect(error.isRetriable).toBe(true)
  })

  it('rejects a well-formed HTTP 200 whose body does not match the schema', async () => {
    // A 200 carrying the wrong shape is the failure TypeScript cannot catch.
    handler = () => ({ status: 200, data: [{ id: 'not-a-number', exercise_name: 'Squat' }] })

    const error = await getPRs().catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('RESPONSE_VALIDATION_FAILED')
  })

  it('survives a response that is not our envelope at all', async () => {
    handler = () => ({ status: 502, data: '<html>Bad Gateway</html>' })

    const error = await getPRs().catch((e) => e)

    expect(error.code).toBe('HTTP_502')
    expect(error.message).toMatch(/something went wrong/i)
  })
})

// ── Silent refresh ────────────────────────────────────────────────────────────

describe('401 handling', () => {
  it('refreshes once and retries the original request', async () => {
    localStorage.setItem(TOKEN_KEY, 'stale-access')
    localStorage.setItem(REFRESH_KEY, 'stored-refresh')

    let sessionsCalls = 0
    handler = (url) => {
      if (url.includes('/api/auth/refresh')) return { status: 200, data: tokenResponse('new') }
      sessionsCalls += 1
      if (sessionsCalls === 1) return { status: 401, data: errorBody('UNAUTHORIZED') }
      return { status: 200, data: [] }
    }

    await expect(getWorkoutSessions()).resolves.toEqual([])

    expect(localStorage.getItem(TOKEN_KEY)).toBe('access-new')
    expect(localStorage.getItem(REFRESH_KEY)).toBe('refresh-new')
    // The retry must carry the NEW token, not the stale one that just failed.
    expect(requests.at(-1)?.auth).toBe('Bearer access-new')
  })

  it('makes only one refresh call when several requests 401 at once', async () => {
    localStorage.setItem(TOKEN_KEY, 'stale-access')
    localStorage.setItem(REFRESH_KEY, 'stored-refresh')

    let refreshCalls = 0
    const seen = new Set<string>()
    handler = (url) => {
      if (url.includes('/api/auth/refresh')) {
        refreshCalls += 1
        return { status: 200, data: tokenResponse('new') }
      }
      // Fail each distinct endpoint once, then succeed.
      if (!seen.has(url)) {
        seen.add(url)
        return { status: 401, data: errorBody('UNAUTHORIZED') }
      }
      return { status: 200, data: [] }
    }

    await Promise.all([getWorkoutSessions(), getPRs()])

    // Two refreshes would burn a rotation and hand one caller a dead token.
    expect(refreshCalls).toBe(1)
  })

  it('recovers when another tab wins the rotation race', async () => {
    localStorage.setItem(TOKEN_KEY, 'stale-access')
    localStorage.setItem(REFRESH_KEY, 'shared-refresh')

    let sessionsCalls = 0
    handler = (url) => {
      if (url.includes('/api/auth/refresh')) {
        // This tab lost: the server already rotated for the sibling tab.
        // Simulate that tab writing its replacement to shared storage.
        localStorage.setItem(TOKEN_KEY, 'access-from-sibling')
        localStorage.setItem(REFRESH_KEY, 'refresh-from-sibling')
        return { status: 401, data: errorBody('REFRESH_RACE', 'Just rotated.') }
      }
      sessionsCalls += 1
      if (sessionsCalls === 1) return { status: 401, data: errorBody('UNAUTHORIZED') }
      return { status: 200, data: [] }
    }

    await expect(getWorkoutSessions()).resolves.toEqual([])

    // The session must survive — this is the whole point of REFRESH_RACE.
    expect(localStorage.getItem(TOKEN_KEY)).toBe('access-from-sibling')
    expect(requests.at(-1)?.auth).toBe('Bearer access-from-sibling')
  })

  it('clears the session when a refresh token is replayed (theft response)', async () => {
    localStorage.setItem(TOKEN_KEY, 'stale-access')
    localStorage.setItem(REFRESH_KEY, 'stolen-refresh')
    localStorage.setItem(USER_KEY, JSON.stringify(VALID_USER))

    handler = (url) => {
      if (url.includes('/api/auth/refresh')) {
        return { status: 401, data: errorBody('REFRESH_REUSE') }
      }
      return { status: 401, data: errorBody('UNAUTHORIZED') }
    }

    await expect(getWorkoutSessions()).rejects.toBeDefined()

    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(REFRESH_KEY)).toBeNull()
    expect(localStorage.getItem(USER_KEY)).toBeNull()
  })

  it('gives up when a race has no winner to wait for', async () => {
    // REFRESH_RACE, but no sibling ever writes a replacement — the session is
    // genuinely unrecoverable and must not hang forever.
    vi.useFakeTimers()
    localStorage.setItem(TOKEN_KEY, 'stale-access')
    localStorage.setItem(REFRESH_KEY, 'orphan-refresh')

    handler = (url) =>
      url.includes('/api/auth/refresh')
        ? { status: 401, data: errorBody('REFRESH_RACE') }
        : { status: 401, data: errorBody('UNAUTHORIZED') }

    const pending = getWorkoutSessions().catch((e) => e)
    await vi.advanceTimersByTimeAsync(4000)
    await pending

    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
    vi.useRealTimers()
  })

  it('does not attempt a refresh when no refresh token is stored', async () => {
    let refreshCalls = 0
    handler = (url) => {
      if (url.includes('/api/auth/refresh')) refreshCalls += 1
      return { status: 401, data: errorBody('UNAUTHORIZED') }
    }

    await expect(getWorkoutSessions()).rejects.toBeDefined()
    expect(refreshCalls).toBe(0)
  })

  it('does not retry a request more than once', async () => {
    localStorage.setItem(TOKEN_KEY, 'stale-access')
    localStorage.setItem(REFRESH_KEY, 'stored-refresh')

    let sessionsCalls = 0
    handler = (url) => {
      if (url.includes('/api/auth/refresh')) return { status: 200, data: tokenResponse('new') }
      sessionsCalls += 1
      return { status: 401, data: errorBody('UNAUTHORIZED') } // never recovers
    }

    await expect(getWorkoutSessions()).rejects.toBeDefined()

    // Original + one retry. Without the _retry guard this loops until the stack
    // gives out.
    expect(sessionsCalls).toBe(2)
  })
})
