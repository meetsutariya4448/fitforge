import { expect, test } from '@playwright/test'

import { signIn, stubApi } from './fixtures/api-stub'

/**
 * Token refresh, from the user's side.
 *
 * The server-side guarantee (exactly one caller can redeem a refresh token) is
 * covered by backend/tests/test_auth_concurrency.py. What only a browser can
 * show is whether the person using the app notices — a correct rotation that
 * still logs someone out for having two tabs open is not a fix.
 */
test.describe('Token refresh', () => {
  test('an expired access token is refreshed without the user noticing', async ({ page }) => {
    const api = await stubApi(page)
    await signIn(page)
    await page.goto('/plans')
    await expect(page.getByText('1 plan generated')).toBeVisible()

    // The access token lapses while the user is sitting on the page.
    api.expireAccessToken()

    // Navigating to the dashboard fetches sessions and PRs — a page that only
    // renders would never exercise the refresh path at all.
    await page.getByRole('button', { name: /Dashboard/ }).first().click()

    await expect(page).toHaveURL(/\/dashboard$/)
    // The requests 401'd, refreshed and retried; the user just sees their data.
    await expect(page.getByRole('heading', { name: 'Your Training Overview' })).toBeVisible()
    await expect(page.getByRole('alert')).toHaveCount(0)
    expect(api.calls['/api/auth/refresh']).toBeGreaterThanOrEqual(1)

    const stored = await page.evaluate(() => localStorage.getItem('fitforge_token'))
    expect(stored).toMatch(/^access-rotated-/)
  })

  test('losing a rotation race to another tab does not end the session', async ({ page }) => {
    await stubApi(page).then((api) => {
      api.expireAccessToken()
      // This tab's refresh will lose: a sibling tab redeemed the shared token
      // first.
      api.loseNextRefreshRace()
    })
    await signIn(page)

    // The sibling tab writes its replacement into shared storage shortly after
    // this tab's refresh is rejected. The client should wait for exactly this
    // rather than tearing the session down.
    await page.addInitScript(() => {
      if (sessionStorage.getItem('e2e-sibling-scheduled')) return
      sessionStorage.setItem('e2e-sibling-scheduled', '1')
      setTimeout(() => {
        localStorage.setItem('fitforge_token', 'access-from-sibling-tab')
        localStorage.setItem('fitforge_refresh_token', 'refresh-from-sibling-tab')
      }, 300)
    })

    await page.goto('/dashboard')

    // Polled, not read once: the sibling's write lands after this page has
    // already rendered, so a single read races it.
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem('fitforge_token')))
      .toBe('access-from-sibling-tab')

    // Still signed in, on the page requested — the loser adopted the winner's
    // token instead of clearing the session and bouncing to /auth.
    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('heading', { name: 'Your Training Overview' })).toBeVisible()
  })

  test('a replayed refresh token signs the user out', async ({ page }) => {
    const api = await stubApi(page)
    await signIn(page)
    await page.goto('/plans')
    await expect(page.getByText('1 plan generated')).toBeVisible()

    // The server treats the token as stolen and cuts off the whole family.
    api.expireAccessToken()
    api.invalidateSession()

    await page.getByRole('button', { name: /Dashboard/ }).first().click()

    // Being signed out here is correct — but it must be a clean redirect to the
    // sign-in page, not a broken page or a silent hang.
    await expect(page).toHaveURL(/\/auth$/, { timeout: 15_000 })
    const token = await page.evaluate(() => localStorage.getItem('fitforge_token'))
    expect(token).toBeNull()
  })
})
