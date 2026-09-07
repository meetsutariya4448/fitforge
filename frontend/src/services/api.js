/**
 * Axios-based API client for the FitForge FastAPI backend.
 *
 * The Vite dev proxy forwards /api/* → http://localhost:8000,
 * so no absolute URL is needed during development.
 *
 * For production, set VITE_API_BASE_URL in your .env file.
 */

import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  headers: { 'Content-Type': 'application/json' },
  timeout: 60_000,
})

// ── Request interceptor: attach JWT if present ─────────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('fitforge_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── Response interceptor: silent token refresh on 401 ─────────────────────
// If a request gets a 401, attempt one silent refresh using the stored
// refresh token. On success, retry the original request with the new
// access token. On failure (missing/expired refresh token), clear storage
// and redirect to /auth.

let _refreshPromise = null  // serialise concurrent refresh attempts in THIS tab

const TOKEN_KEY = 'fitforge_token'
const REFRESH_KEY = 'fitforge_refresh_token'
const USER_KEY = 'fitforge_user'

// How long to wait for another tab to finish rotating before giving up.
const SIBLING_ROTATION_TIMEOUT_MS = 3000
const SIBLING_POLL_INTERVAL_MS = 50

function _clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem(USER_KEY)
  if (window.location.pathname !== '/auth') window.location.href = '/auth'
}

function _storeSession(data) {
  localStorage.setItem(TOKEN_KEY, data.access_token)
  localStorage.setItem(REFRESH_KEY, data.refresh_token)
  if (data.user) localStorage.setItem(USER_KEY, JSON.stringify(data.user))
}

/**
 * Wait for another tab to finish rotating the refresh token.
 *
 * _refreshPromise only serialises within one tab. Two tabs hold the same
 * refresh token in shared localStorage, so both can redeem it at once — and
 * the server, which now rotates atomically, lets exactly one win. The loser
 * gets 401 REFRESH_RACE, which means "your session is fine, someone else
 * rotated first". Recovering is a matter of waiting for the winner to write
 * the new token to localStorage rather than tearing the session down.
 *
 * Resolves with the fresh access token, or null if nothing arrived in time.
 */
function _awaitSiblingRotation(sentRefreshToken) {
  return new Promise((resolve) => {
    const deadline = Date.now() + SIBLING_ROTATION_TIMEOUT_MS
    const check = () => {
      const current = localStorage.getItem(REFRESH_KEY)
      // A different refresh token than the one we sent means the winning tab
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

function _errorCode(error) {
  return error?.response?.data?.error?.code
}

/**
 * Redeem the stored refresh token for a new pair. Returns the new access
 * token. Throws if the session is genuinely over.
 */
async function _performRefresh() {
  const sent = localStorage.getItem(REFRESH_KEY)
  try {
    const { data } = await apiClient.post('/api/auth/refresh', { refresh_token: sent })
    _storeSession(data)
    return data.access_token
  } catch (error) {
    if (_errorCode(error) === 'REFRESH_RACE') {
      const token = await _awaitSiblingRotation(sent)
      if (token) return token
    }
    // REFRESH_REUSE, REFRESH_EXPIRED, REFRESH_INVALID, or a race whose winner
    // never landed — the session really is over.
    throw error
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Only attempt refresh once per request (_retry flag) and only on 401s
    // that are not themselves the refresh endpoint (avoid infinite loops).
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/api/auth/refresh')
    ) {
      originalRequest._retry = true

      if (!localStorage.getItem(REFRESH_KEY)) {
        _clearSession()
        return Promise.reject(error)
      }

      try {
        // Serialise: if multiple requests 401 simultaneously, only one
        // refresh call is made; others wait for the same promise.
        if (!_refreshPromise) {
          _refreshPromise = _performRefresh().finally(() => { _refreshPromise = null })
        }

        const accessToken = await _refreshPromise

        // Retry original request with the new access token.
        originalRequest.headers.Authorization = `Bearer ${accessToken}`
        return apiClient(originalRequest)
      } catch {
        _clearSession()
        return Promise.reject(error)
      }
    }

    return Promise.reject(error)
  },
)

// ── Auth endpoints ────────────────────────────────────────────────────────────

export const register = async (payload) => {
  const { data } = await apiClient.post('/api/auth/register', payload)
  return data
}

export const login = async (payload) => {
  const { data } = await apiClient.post('/api/auth/login', payload)
  return data
}

export const loginDemo = async () => {
  const { data } = await apiClient.post('/api/auth/login', {
    email: 'demo@fitforge.app',
    password: 'Demo1234!',
  })
  return data
}

// ── Workout endpoints ────────────────────────────────────────────────────────

export const generateWorkoutPlan = async (onboardingData) => {
  const { data } = await apiClient.post('/api/workout/generate', onboardingData)
  return data
}

export const getWorkoutHistory = async () => {
  const { data } = await apiClient.get('/api/workout/history')
  return data
}

// ── Session endpoints ─────────────────────────────────────────────────────────

export const logWorkoutSession = async (sessionData) => {
  const { data } = await apiClient.post('/api/sessions', sessionData)
  return data
}

export const getWorkoutSessions = async () => {
  const { data } = await apiClient.get('/api/sessions')
  return data
}

export const getExerciseTrend = async (exerciseName) => {
  const { data } = await apiClient.get(
    `/api/sessions/exercise/${encodeURIComponent(exerciseName)}`
  )
  return data
}

// ── Personal Records endpoints ────────────────────────────────────────────────

export const getPRs = async () => {
  const { data } = await apiClient.get('/api/prs')
  return data
}

export default apiClient
