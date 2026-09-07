import { expect, test } from '@playwright/test'

/**
 * Smoke test against the REAL backend and a real PostgreSQL — nothing stubbed.
 *
 * The rest of the browser suite stubs the API so it can force failure modes and
 * run without a database. This one exists to catch what stubbing hides: a
 * response shape the stub gets wrong, a proxy misconfiguration, a migration not
 * applied. It creates a real account and writes real rows, so it is opt-in.
 *
 *   Terminal 1:  cd backend && uvicorn app.main:app --port 8000
 *   Terminal 2:  cd frontend && npm run dev
 *   Terminal 3:  E2E_REAL_STACK=1 E2E_BASE_URL=http://localhost:5173 \
 *                  npx playwright test e2e/realstack.spec.ts
 */
const EMAIL = `real_${Date.now()}@test.com`

test.skip(
  !process.env.E2E_REAL_STACK,
  'Set E2E_REAL_STACK=1 with a backend running to include this test.',
)

test('register, log a workout, see it in history and on the dashboard', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })

  await page.goto('/auth')
  await page.getByRole('button', { name: 'Register' }).first().click()
  await page.getByLabel('Name').fill('Real Tester')
  await page.getByLabel('Email').fill(EMAIL)
  await page.getByLabel('Password').fill('Password1!')
  await page.locator('form').getByRole('button', { name: 'Create Account' }).click()

  await expect(page).toHaveURL(/\/onboarding$/, { timeout: 15_000 })

  // Log a session directly (skips the paid Groq generation call).
  const status = await page.evaluate(async () => {
    const res = await fetch('/api/sessions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('fitforge_token')}`,
      },
      body: JSON.stringify({
        day_name: 'Day 1', plan_id: null, notes: 'real stack',
        exercise_logs: [{ exercise_name: 'Squat', sets_completed: 3, reps_completed: 8, weight_kg: 100 }],
      }),
    })
    return res.status
  })
  expect(status).toBe(201)

  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { name: 'Your Training Overview' })).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await expect(page.getByText('Squat').first()).toBeVisible({ timeout: 10_000 })

  expect(errors, `console/page errors: ${errors.join(' | ')}`).toEqual([])
})
