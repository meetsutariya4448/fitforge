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
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60_000,  // 60 s — AI generation can take a moment
})

// ── Request interceptor: attach JWT if present ─────────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('fitforge_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: handle 401 globally ────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid — clear local storage
      localStorage.removeItem('fitforge_token')
    }
    return Promise.reject(error)
  },
)

// ── Workout endpoints ────────────────────────────────────────────────────────

/**
 * Generate a personalised workout plan from onboarding data.
 *
 * @param {Object} onboardingData - Matches the OnboardingData Pydantic schema
 * @returns {Promise<{success: boolean, plan: Object}>}
 */
export const generateWorkoutPlan = async (onboardingData) => {
  const { data } = await apiClient.post('/api/workout/generate', onboardingData)
  return data
}

// ── Auth endpoints (stubs for Module 2) ──────────────────────────────────────

export const register = async (payload) => {
  const { data } = await apiClient.post('/api/auth/register', payload)
  return data
}

export const login = async (payload) => {
  const { data } = await apiClient.post('/api/auth/login', payload)
  return data
}

export default apiClient
