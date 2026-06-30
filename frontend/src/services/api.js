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

// ── Response interceptor: handle 401 globally ────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('fitforge_token')
      localStorage.removeItem('fitforge_user')
      if (window.location.pathname !== '/auth') window.location.href = '/auth'
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
