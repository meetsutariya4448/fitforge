/**
 * Authentication state for the whole app.
 *
 * Before this, seven files read and wrote localStorage directly and each page
 * guarded itself with its own `useEffect` redirect. Nothing kept them in step:
 * logging out in the navbar left other mounted components holding a user object
 * that no longer existed, and a session cleared by the API client (expired
 * refresh token) was invisible to React until the next full page load.
 *
 * Here the stored session is read once, held in state, and exposed through one
 * hook. Storage is still the source of truth across reloads and tabs — the API
 * client reads and rotates tokens there — so this listens for `storage` events
 * and stays in step with the tab that rotated.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import {
  clearSession,
  login as apiLogin,
  loginDemo as apiLoginDemo,
  logout as apiLogout,
  register as apiRegister,
  REFRESH_KEY,
  TOKEN_KEY,
  USER_KEY,
  type LoginPayload,
  type RegisterPayload,
} from '../services/api'
import { userSchema, type TokenResponse, type User } from '../schemas/api'

interface AuthContextValue {
  user: User | null
  isAuthenticated: boolean
  /** True until the stored session has been read — routes must not redirect yet. */
  isLoading: boolean
  login: (payload: LoginPayload) => Promise<User>
  loginDemo: () => Promise<User>
  register: (payload: RegisterPayload) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

/**
 * Read the persisted user, tolerating a corrupt or half-written entry.
 *
 * localStorage holds whatever was last written, including values from an older
 * version of this app. Parsing through the schema means a bad entry logs the
 * user out cleanly instead of crashing the first component to touch `user.name`.
 */
function readStoredUser(): User | null {
  const token = localStorage.getItem(TOKEN_KEY)
  const raw = localStorage.getItem(USER_KEY)
  if (!token || !raw) return null

  try {
    const parsed = userSchema.safeParse(JSON.parse(raw))
    if (parsed.success) return parsed.data
  } catch {
    // Fall through: unparseable JSON is treated the same as no session.
  }
  clearSession()
  return null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    setUser(readStoredUser())
    setIsLoading(false)
  }, [])

  // Another tab logging in or out, or the API client rotating tokens, changes
  // storage without touching this tab's React state. `storage` fires only in
  // other tabs, which is exactly the case local state cannot observe.
  useEffect(() => {
    const onStorage = (event: StorageEvent): void => {
      if (event.key !== null && event.key !== TOKEN_KEY && event.key !== USER_KEY) return
      setUser(readStoredUser())
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const adopt = useCallback((response: TokenResponse): User => {
    localStorage.setItem(TOKEN_KEY, response.access_token)
    localStorage.setItem(REFRESH_KEY, response.refresh_token)
    localStorage.setItem(USER_KEY, JSON.stringify(response.user))
    setUser(response.user)
    return response.user
  }, [])

  const login = useCallback(
    async (payload: LoginPayload) => adopt(await apiLogin(payload)),
    [adopt],
  )

  const loginDemo = useCallback(async () => adopt(await apiLoginDemo()), [adopt])

  const register = useCallback(
    async (payload: RegisterPayload) => adopt(await apiRegister(payload)),
    [adopt],
  )

  const logout = useCallback(async () => {
    // Revoke server-side first so the refresh token cannot be replayed, but
    // clear locally regardless of whether that call succeeds.
    await apiLogout()
    clearSession()
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      login,
      loginDemo,
      register,
      logout,
    }),
    [user, isLoading, login, loginDemo, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
