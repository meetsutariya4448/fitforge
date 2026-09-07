/**
 * Route guard for pages that need a signed-in user.
 *
 * Replaces the per-page `useEffect(() => { if (!token) navigate('/') })`
 * pattern, which rendered the protected page for a frame before redirecting and
 * disagreed about the destination (`/` in some pages, `/auth` in others).
 *
 * Redirects carry the attempted location so signing in can return the user
 * where they were headed instead of dropping them on a default page.
 */

import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'

import { useAuth } from '../contexts/AuthContext'

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  // The stored session has not been read yet. Redirecting now would bounce a
  // signed-in user to /auth on every hard refresh.
  if (isLoading) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex min-h-screen items-center justify-center text-slate-400"
      >
        <span className="sr-only">Loading your session</span>
        <div
          aria-hidden="true"
          className="h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-emerald-500"
        />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth" replace state={{ from: location }} />
  }

  return <>{children}</>
}
