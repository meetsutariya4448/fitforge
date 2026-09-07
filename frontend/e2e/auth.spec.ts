import { expect, test } from '@playwright/test'

import { DEMO_USER, signIn, stubApi } from './fixtures/api-stub'

test.describe('Login', () => {
  test('signing in takes a returning user to their plans', async ({ page }) => {
    await stubApi(page)
    await page.goto('/auth')

    await page.getByLabel('Email').fill('demo@fitforge.app')
    await page.getByLabel('Password').fill('Demo1234!')
    // Scoped to the form: "Log In" also names the tab above it.
    await page.locator('form').getByRole('button', { name: 'Log In' }).click()

    await expect(page).toHaveURL(/\/plans$/)
    // The navbar reflects the new session immediately — it reads auth context,
    // not localStorage, so it no longer needs a page reload to notice.
    await expect(page.getByText(DEMO_USER.name.split(' ')[0]!)).toBeVisible()
  })

  test('a rejected login shows the reason the server gave', async ({ page }) => {
    await page.route('**/api/auth/login', (route) =>
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          error: { code: 'UNAUTHORIZED', message: 'Invalid email or password.' },
        }),
      }),
    )
    await page.goto('/auth')

    await page.getByLabel('Email').fill('wrong@example.com')
    await page.getByLabel('Password').fill('nope12345')
    await page.locator('form').getByRole('button', { name: 'Log In' }).click()

    // Not the generic fallback: the client used to read a `detail` field the
    // API never sends, so every failure looked identical.
    await expect(page.getByRole('alert')).toHaveText('Invalid email or password.')
    await expect(page).toHaveURL(/\/auth$/)
  })

  test('a protected page sends a signed-out visitor to sign in', async ({ page }) => {
    await stubApi(page)
    await page.goto('/dashboard')

    await expect(page).toHaveURL(/\/auth$/)
  })

  test('a signed-in user reloading a protected page stays put', async ({ page }) => {
    await stubApi(page)
    await signIn(page)

    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/dashboard$/)

    // RequireAuth waits for stored session to load before deciding; without
    // that wait, a hard refresh bounces the user to /auth.
    await page.reload()
    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('heading', { name: 'Your Training Overview' })).toBeVisible()
  })

  test('logging out clears the session and the navbar', async ({ page }) => {
    await stubApi(page)
    await signIn(page)
    await page.goto('/dashboard')

    await page.getByRole('button', { name: /Logout/ }).click()

    await expect(page).toHaveURL('/')
    await expect(page.getByRole('button', { name: /Login/ })).toBeVisible()
    const token = await page.evaluate(() => localStorage.getItem('fitforge_token'))
    expect(token).toBeNull()
  })
})
