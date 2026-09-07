import { expect, test } from '@playwright/test'

import { signIn, stubApi } from './fixtures/api-stub'

/**
 * What the app does when the API does not cooperate.
 *
 * The bar is not "does not crash" — it is that the user can tell what happened
 * and what to do next. The dashboard failure below is the clearest case: it used
 * to render a load failure as an empty dashboard, so a network problem was
 * indistinguishable from having logged nothing, and the empty state cheerfully
 * invited the user to start training.
 */
test.describe('Graceful API failure', () => {
  test('a failing dashboard load says so instead of showing an empty dashboard', async ({ page }) => {
    await stubApi(page, { failing: { '/api/sessions': 500, '/api/prs': 500 } })
    await signIn(page)
    await page.goto('/dashboard')

    const alert = page.getByRole('alert')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText(/loading problem, not lost data/i)
    await expect(page.getByRole('button', { name: /Try again/ })).toBeVisible()

    // The encouraging empty state must NOT appear — it would be a lie.
    await expect(page.getByText(/log your first workout/i)).toHaveCount(0)
  })

  test('a network drop is reported as a connection problem', async ({ page }) => {
    // status 0 tells the stub to abort the request outright.
    await stubApi(page, { failing: { '/api/workout/history': 0 } })
    await signIn(page)
    await page.goto('/plans')

    await expect(page.getByRole('alert')).toContainText(/could not reach the server/i)
  })

  test('a failed plan generation keeps the user on the form with their answers', async ({ page }) => {
    await stubApi(page, { failing: { '/api/workout/generate': 500 } })
    await signIn(page)
    await page.goto('/onboarding')

    await page.getByLabel('First name').fill('Demo')
    await page.getByLabel('Age').fill('29')
    await page.getByRole('button', { name: 'Continue' }).click()
    await page.getByRole('radio', { name: /Build Muscle/ }).click()
    await page.getByRole('button', { name: 'Continue' }).click()
    await page.getByRole('radio', { name: /Intermediate/ }).click()
    await page.getByRole('button', { name: 'Continue' }).click()
    await page.getByRole('checkbox', { name: /Barbell/ }).click()
    await page.getByRole('button', { name: 'Continue' }).click()
    await page.getByRole('button', { name: 'Generate My Plan' }).click()

    await expect(page.getByRole('alert')).toBeVisible()
    // Still on the wizard, and the loading overlay is gone — a spinner that
    // never stops is worse than an error.
    await expect(page).toHaveURL(/\/onboarding$/)
    await expect(page.getByText(/Building your personalised plan/)).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Generate My Plan' })).toBeEnabled()
  })

  test('a failing save keeps the modal open with the entered values', async ({ page }) => {
    await stubApi(page, { failing: { '/api/sessions': 500 } })
    await signIn(page)
    await page.goto('/plans')
    await page.getByRole('button', { name: /View Plan/ }).click()
    await page.getByRole('button', { name: /Log This Workout/ }).first().click()

    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('Weight in kilograms for Bench Press').fill('82.5')
    await dialog.getByRole('button', { name: 'Save Session' }).click()

    await expect(page.getByText(/something went wrong on our end/i)).toBeVisible()
    await expect(dialog).toBeVisible()
    // Losing the numbers on a failed save would mean re-entering the workout.
    await expect(dialog.getByLabel('Weight in kilograms for Bench Press')).toHaveValue('82.5')
  })

  test('a malformed response is refused rather than rendered', async ({ page }) => {
    await signIn(page)
    await page.route('**/api/workout/history', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        // A 200 with the wrong shape — exactly what types alone cannot catch.
        body: JSON.stringify({ plans: [{ id: 'not-a-number' }], total: 'one' }),
      }),
    )
    await page.goto('/plans')

    await expect(page.getByRole('alert')).toContainText(/could not understand/i)
  })
})
