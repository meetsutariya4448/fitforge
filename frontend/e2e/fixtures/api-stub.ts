/**
 * A stub FitForge API, served through Playwright's request interception.
 *
 * Running these flows against the real backend would mean a database, a Groq
 * key, and a plan-generation call per test — slow, costly, and non-deterministic
 * in ways that have nothing to do with the frontend. The stub answers with the
 * same shapes the real API does (they are checked against its OpenAPI document
 * by scripts/check-api-contract.mjs), and lets a test say "this next refresh
 * loses the race" or "this endpoint is down", which is the whole point.
 */

import type { Page, Route } from '@playwright/test'

export const DEMO_USER = { id: 1, email: 'demo@fitforge.app', name: 'Demo User' }

export const PLAN = {
  title: '3-Day Intermediate Muscle Building Plan',
  summary: 'A balanced three-day split focused on compound lifts.',
  generated_for: 'Demo',
  general_tips: ['Sleep 7-9 hours', 'Eat enough protein'],
  citations: ['[1] ACSM rep ranges for hypertrophy'],
  grounded: true,
  days: [
    {
      day: 'Day 1',
      focus: 'Upper Body',
      duration_minutes: 45,
      warmup_notes: 'Five minutes of light cardio.',
      cooldown_notes: null,
      exercises: [
        { name: 'Bench Press', sets: 4, reps: '8-10', rest_seconds: 90, notes: 'Keep shoulders back' },
        { name: 'Barbell Row', sets: 4, reps: '8-10', rest_seconds: 90, notes: null },
      ],
    },
    {
      day: 'Day 2',
      focus: 'Lower Body',
      duration_minutes: 50,
      warmup_notes: null,
      cooldown_notes: null,
      exercises: [{ name: 'Back Squat', sets: 5, reps: '5', rest_seconds: 150, notes: null }],
    },
  ],
}

export const HISTORY_ITEM = {
  id: 42,
  goal: 'build_muscle',
  fitness_level: 'intermediate',
  days_per_week: 3,
  created_at: '2026-09-01T10:00:00Z',
  plan_json: PLAN,
}

export const SESSION = {
  id: 100,
  day_name: 'Day 1',
  plan_id: 42,
  notes: null,
  session_date: '2026-09-05T18:00:00Z',
  created_at: '2026-09-05T18:00:00Z',
  exercise_logs: [
    {
      id: 1,
      exercise_name: 'Bench Press',
      sets_completed: 4,
      reps_completed: 8,
      weight_kg: 80,
      created_at: '2026-09-05T18:00:00Z',
    },
  ],
}

export const PR = {
  id: 1,
  exercise_name: 'Bench Press',
  max_weight_kg: 80,
  max_reps: 8,
  achieved_at: '2026-09-05T18:00:00Z',
}

function tokens(suffix: string) {
  return {
    access_token: `access-${suffix}`,
    refresh_token: `refresh-${suffix}`,
    token_type: 'bearer',
    user: DEMO_USER,
  }
}

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

function apiError(route: Route, status: number, code: string, message: string) {
  return json(route, status, { error: { code, message } })
}

export interface StubOptions {
  /** Endpoints that should fail, mapped to the status to answer with. */
  failing?: Record<string, number>
  /** Sessions the stubbed account has already logged. */
  sessions?: unknown[]
}

export interface StubControls {
  /** Number of times each endpoint was called. */
  calls: Record<string, number>
  /** Make the access token appear expired until the next refresh succeeds. */
  expireAccessToken: () => void
  /** Make the next refresh answer 401 REFRESH_RACE, as a losing tab would see. */
  loseNextRefreshRace: () => void
  /** Make every refresh answer 401 REFRESH_REUSE — the session is over. */
  invalidateSession: () => void
  savedSessions: unknown[]
}

/**
 * Install the stub. Returns controls a test can use to steer failure modes.
 */
export async function stubApi(page: Page, options: StubOptions = {}): Promise<StubControls> {
  const controls: StubControls = {
    calls: {},
    expireAccessToken: () => {
      expiredTokens.add(issuedToken)
    },
    loseNextRefreshRace: () => {
      raceNextRefresh = true
    },
    invalidateSession: () => {
      sessionInvalidated = true
    },
    savedSessions: [...(options.sessions ?? [])],
  }

  // Which access tokens are no longer accepted. Modelling expiry per token,
  // rather than as one global flag, is what lets a test show a client
  // recovering by adopting a *different* token — the whole point of the
  // cross-tab race case.
  const expiredTokens = new Set<string>()
  let issuedToken = 'access-initial'
  let raceNextRefresh = false
  let sessionInvalidated = false
  let rotation = 0

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    controls.calls[path] = (controls.calls[path] ?? 0) + 1

    const forcedFailure = options.failing?.[path]
    // Compared against undefined, not truthiness: 0 is a meaningful value here
    // (abort the request outright, as a dropped connection would).
    if (forcedFailure !== undefined) {
      if (forcedFailure === 0) return route.abort('failed')
      return apiError(route, forcedFailure, 'INTERNAL_ERROR', 'Something went wrong on our end.')
    }

    // ── Auth ──
    if (path === '/api/auth/login' || path === '/api/auth/register') {
      issuedToken = 'access-initial'
      expiredTokens.delete(issuedToken)
      return json(route, path.endsWith('register') ? 201 : 200, tokens('initial'))
    }

    if (path === '/api/auth/refresh') {
      if (sessionInvalidated) {
        return apiError(route, 401, 'REFRESH_REUSE', 'Refresh token invalid or expired.')
      }
      if (raceNextRefresh) {
        raceNextRefresh = false
        return apiError(
          route,
          401,
          'REFRESH_RACE',
          'This refresh token was just rotated by a concurrent request.',
        )
      }
      rotation += 1
      issuedToken = `access-rotated-${rotation}`
      return json(route, 200, tokens(`rotated-${rotation}`))
    }

    if (path === '/api/auth/logout') return route.fulfill({ status: 204, body: '' })

    // ── Everything below is authenticated ──
    const bearer = (request.headers()['authorization'] ?? '').replace(/^Bearer /, '')
    if (expiredTokens.has(bearer)) {
      return apiError(route, 401, 'UNAUTHORIZED', 'Could not validate credentials')
    }

    if (path === '/api/auth/me') return json(route, 200, DEMO_USER)

    if (path === '/api/workout/generate') return json(route, 200, { success: true, plan: PLAN })

    if (path === '/api/workout/history') {
      return json(route, 200, { plans: [HISTORY_ITEM], total: 1, next_cursor: null })
    }

    if (path === '/api/sessions' && request.method() === 'POST') {
      const body = request.postDataJSON()
      const saved = { ...SESSION, day_name: body.day_name, notes: body.notes ?? null }
      controls.savedSessions.push(body)
      return json(route, 201, saved)
    }

    if (path === '/api/sessions') return json(route, 200, controls.savedSessions.length ? [SESSION] : [])

    if (path.startsWith('/api/sessions/exercise/')) {
      return json(route, 200, {
        exercise_name: decodeURIComponent(path.split('/').pop() ?? ''),
        data: [
          { date: '2026-09-01T10:00:00Z', max_weight_kg: 75, total_volume: 2400 },
          { date: '2026-09-05T18:00:00Z', max_weight_kg: 80, total_volume: 2560 },
        ],
      })
    }

    if (path === '/api/prs') return json(route, 200, [PR])

    return json(route, 404, { error: { code: 'NOT_FOUND', message: 'No stub for this route.' } })
  })

  return controls
}

/**
 * Start the tab signed in, skipping the login screen.
 *
 * Seeded once per tab, not once per navigation: addInitScript runs on every
 * document, so an unguarded version would silently re-create the session the
 * app had just cleared — and a test asserting that logout or a stolen-token
 * response clears storage would pass or fail for the wrong reason. The
 * sessionStorage marker survives same-tab navigations, which is exactly the
 * scope wanted.
 */
export async function signIn(page: Page): Promise<void> {
  await page.addInitScript((user) => {
    if (sessionStorage.getItem('e2e-session-seeded')) return
    sessionStorage.setItem('e2e-session-seeded', '1')
    localStorage.setItem('fitforge_token', 'access-initial')
    localStorage.setItem('fitforge_refresh_token', 'refresh-initial')
    localStorage.setItem('fitforge_user', JSON.stringify(user))
  }, DEMO_USER)
}
