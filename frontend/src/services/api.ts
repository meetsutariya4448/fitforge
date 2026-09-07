/**
 * Axios-based API client for the FitForge FastAPI backend.
 *
 * The Vite dev proxy forwards /api/* → http://localhost:8000,
 * so no absolute URL is needed during development.
 *
 * For production, set VITE_API_BASE_URL in your .env file.
 *
 * Every exported call parses its response through a zod schema from
 * schemas/api.ts before returning, so callers receive data that has actually
 * been checked rather than data that merely has a type annotation.
 */

import axios, {
  AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios'
import { z } from 'zod'

import {
  apiErrorSchema,
  exerciseTrendResponseSchema,
  prListSchema,
  sessionListSchema,
  sessionResponseSchema,
  tokenResponseSchema,
  workoutHistoryResponseSchema,
  workoutPlanResponseSchema,
  type ExerciseTrendResponse,
  type OnboardingData,
  type PersonalRecord,
  type SessionCreate,
  type SessionResponse,
  type TokenResponse,
  type User,
  type WorkoutHistoryResponse,
  type WorkoutPlanResponse,
} from '../schemas/api'

// Axios keeps no room for our own flags on a request config, so widen it.
interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  headers: { 'Content-Type': 'application/json' },
  timeout: 60_000,
})

// ── Storage keys ──────────────────────────────────────────────────────────────

export const TOKEN_KEY = 'fitforge_token'
export const REFRESH_KEY = 'fitforge_refresh_token'
export const USER_KEY = 'fitforge_user'

// ── Error handling ────────────────────────────────────────────────────────────

/**
 * A failure the UI can actually render.
 *
 * The API answers errors with {"error": {code, message}}. The frontend used to
 * read `data.detail`, which that envelope has never contained, so every server
 * message resolved to undefined and users only ever saw a generic fallback.
 * Normalising here means components have one thing to display and one field to
 * branch on.
 */
export class ApiError extends Error {
  readonly code: string
  readonly status: number | null
  readonly retryAfter: number | null

  constructor(code: string, message: string, status: number | null, retryAfter: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.retryAfter = retryAfter
  }

  /** True when retrying the same request could plausibly succeed. */
  get isRetriable(): boolean {
    return this.status === null || this.status >= 500 || this.status === 429
  }
}

const NETWORK_ERROR_MESSAGE =
  'Could not reach the server. Check your connection and try again.'
const UNEXPECTED_SHAPE_MESSAGE =
  'The server sent a response this app could not understand. Please try again.'

/** Convert anything thrown by axios or zod into an ApiError. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  if (error instanceof z.ZodError) {
    // A schema mismatch is a contract bug, not a user error. Surface a calm
    // message but keep the field paths in the console for whoever debugs it.
    console.error('API response failed validation:', error.issues)
    return new ApiError('RESPONSE_VALIDATION_FAILED', UNEXPECTED_SHAPE_MESSAGE, null)
  }

  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError
    const status = axiosError.response?.status ?? null

    if (!axiosError.response) {
      const code = axiosError.code === 'ECONNABORTED' ? 'TIMEOUT' : 'NETWORK_ERROR'
      return new ApiError(code, NETWORK_ERROR_MESSAGE, null)
    }

    const parsed = apiErrorSchema.safeParse(axiosError.response.data)
    if (parsed.success) {
      const { code, message, retry_after } = parsed.data.error
      return new ApiError(code, message, status, retry_after ?? null)
    }

    // A response we did not shape — a proxy's HTML 502, most likely.
    return new ApiError(
      `HTTP_${status ?? 'UNKNOWN'}`,
      'Something went wrong. Please try again.',
      status,
    )
  }

  return new ApiError('UNKNOWN', 'Something went wrong. Please try again.', null)
}

// ── Request interceptor: attach JWT if present ────────────────────────────────

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── Response interceptor: silent token refresh on 401 ─────────────────────────

let refreshPromise: Promise<string> | null = null // serialises refreshes in THIS tab

// How long to wait for another tab to finish rotating before giving up.
const SIBLING_ROTATION_TIMEOUT_MS = 3000
const SIBLING_POLL_INTERVAL_MS = 50

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem(USER_KEY)
}

function redirectToAuth(): void {
  if (window.location.pathname !== '/auth') window.location.href = '/auth'
}

function storeSession(data: TokenResponse): void {
  localStorage.setItem(TOKEN_KEY, data.access_token)
  localStorage.setItem(REFRESH_KEY, data.refresh_token)
  localStorage.setItem(USER_KEY, JSON.stringify(data.user))
}

/**
 * Wait for another tab to finish rotating the refresh token.
 *
 * `refreshPromise` only serialises within one tab. Two tabs share the same
 * refresh token via localStorage, so both can redeem it at once — and the
 * server, which rotates atomically, lets exactly one win. The loser gets
 * 401 REFRESH_RACE, meaning "your session is fine, someone else rotated
 * first". Recovering is a matter of waiting for the winner to write the new
 * token, not tearing the session down.
 *
 * Resolves with the fresh access token, or null if nothing arrived in time.
 */
function awaitSiblingRotation(sentRefreshToken: string | null): Promise<string | null> {
  return new Promise((resolve) => {
    const deadline = Date.now() + SIBLING_ROTATION_TIMEOUT_MS
    const check = (): void => {
      const current = localStorage.getItem(REFRESH_KEY)
      // A refresh token different from the one we sent means the winning tab
      // has already stored its replacement.
      if (current && current !== sentRefreshToken) {
        resolve(localStorage.getItem(TOKEN_KEY))
        return
      }
      if (Date.now() >= deadline) {
        resolve(null)
        return
      }
      setTimeout(check, SIBLING_POLL_INTERVAL_MS)
    }
    check()
  })
}

/**
 * Redeem the stored refresh token for a new pair, returning the new access
 * token. Throws when the session is genuinely over.
 */
async function performRefresh(): Promise<string> {
  const sent = localStorage.getItem(REFRESH_KEY)
  try {
    const { data } = await apiClient.post('/api/auth/refresh', { refresh_token: sent })
    const parsed = tokenResponseSchema.parse(data)
    storeSession(parsed)
    return parsed.access_token
  } catch (error) {
    if (toApiError(error).code === 'REFRESH_RACE') {
      const token = await awaitSiblingRotation(sent)
      if (token) return token
    }
    // REFRESH_REUSE, REFRESH_EXPIRED, REFRESH_INVALID, or a race whose winner
    // never landed — the session really is over.
    throw error
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetriableConfig | undefined

    // Only attempt refresh once per request (_retry flag) and only on 401s
    // that are not themselves the refresh endpoint (avoid infinite loops).
    if (
      originalRequest &&
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/api/auth/refresh')
    ) {
      originalRequest._retry = true

      if (!localStorage.getItem(REFRESH_KEY)) {
        clearSession()
        redirectToAuth()
        return Promise.reject(error)
      }

      try {
        if (!refreshPromise) {
          refreshPromise = performRefresh().finally(() => {
            refreshPromise = null
          })
        }

        const accessToken = await refreshPromise
        originalRequest.headers.Authorization = `Bearer ${accessToken}`
        return await apiClient(originalRequest)
      } catch {
        clearSession()
        redirectToAuth()
        return Promise.reject(error)
      }
    }

    return Promise.reject(error)
  },
)

// ── Request helper ────────────────────────────────────────────────────────────

/**
 * Run a request and validate its response, converting every failure mode —
 * network, HTTP, and schema mismatch — into an ApiError.
 */
async function request<S extends z.ZodTypeAny>(
  schema: S,
  run: () => Promise<{ data: unknown }>,
): Promise<z.infer<S>> {
  // Inferring the return type from the schema rather than taking it as a
  // separate parameter matters for schemas using .default(): their input and
  // output types differ, and pinning only one of them makes the two disagree.
  try {
    const { data } = await run()
    return schema.parse(data) as z.infer<S>
  } catch (error) {
    throw toApiError(error)
  }
}

// ── Auth endpoints ────────────────────────────────────────────────────────────

export interface RegisterPayload {
  email: string
  password: string
  name: string
}

export interface LoginPayload {
  email: string
  password: string
}

export const register = (payload: RegisterPayload): Promise<TokenResponse> =>
  request(tokenResponseSchema, () => apiClient.post('/api/auth/register', payload))

export const login = (payload: LoginPayload): Promise<TokenResponse> =>
  request(tokenResponseSchema, () => apiClient.post('/api/auth/login', payload))

export const loginDemo = (): Promise<TokenResponse> =>
  login({ email: 'demo@fitforge.app', password: 'Demo1234!' })

export const logout = async (): Promise<void> => {
  const refreshToken = localStorage.getItem(REFRESH_KEY)
  if (!refreshToken) return
  try {
    await apiClient.post('/api/auth/logout', { refresh_token: refreshToken })
  } catch {
    // Logout is best-effort: the local session is cleared either way, and a
    // failed revoke must not strand the user on a page they cannot leave.
  }
}

// ── Workout endpoints ─────────────────────────────────────────────────────────

export const generateWorkoutPlan = (
  onboardingData: OnboardingData,
): Promise<WorkoutPlanResponse> =>
  request(workoutPlanResponseSchema, () =>
    apiClient.post('/api/workout/generate', onboardingData),
  )

export const getWorkoutHistory = (cursor?: number): Promise<WorkoutHistoryResponse> =>
  request(workoutHistoryResponseSchema, () =>
    apiClient.get('/api/workout/history', { params: cursor ? { cursor } : undefined }),
  )

// ── Session endpoints ─────────────────────────────────────────────────────────

export const logWorkoutSession = (sessionData: SessionCreate): Promise<SessionResponse> =>
  request(sessionResponseSchema, () => apiClient.post('/api/sessions', sessionData))

export const getWorkoutSessions = (): Promise<SessionResponse[]> =>
  request(sessionListSchema, () => apiClient.get('/api/sessions'))

export const getExerciseTrend = (exerciseName: string): Promise<ExerciseTrendResponse> =>
  request(exerciseTrendResponseSchema, () =>
    apiClient.get(`/api/sessions/exercise/${encodeURIComponent(exerciseName)}`),
  )

// ── Personal Records endpoints ────────────────────────────────────────────────

export const getPRs = (): Promise<PersonalRecord[]> =>
  request(prListSchema, () => apiClient.get('/api/prs'))

export type { User }
export default apiClient
