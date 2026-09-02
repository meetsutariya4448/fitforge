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

let _refreshPromise = null  // serialise concurrent refresh attempts

function _clearSession() {
  localStorage.removeItem('fitforge_token')
  localStorage.removeItem('fitforge_refresh_token')
  localStorage.removeItem('fitforge_user')
  if (window.location.pathname !== '/auth') window.location.href = '/auth'
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

      const refreshToken = localStorage.getItem('fitforge_refresh_token')
      if (!refreshToken) {
        _clearSession()
        return Promise.reject(error)
      }

      try {
        // Serialise: if multiple requests 401 simultaneously, only one
        // refresh call is made; others wait for the same promise.
        if (!_refreshPromise) {
          _refreshPromise = apiClient
            .post('/api/auth/refresh', { refresh_token: refreshToken })
            .finally(() => { _refreshPromise = null })
        }

        const { data } = await _refreshPromise
        localStorage.setItem('fitforge_token', data.access_token)
        localStorage.setItem('fitforge_refresh_token', data.refresh_token)
        if (data.user) localStorage.setItem('fitforge_user', JSON.stringify(data.user))

        // Retry original request with the new access token.
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`
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
