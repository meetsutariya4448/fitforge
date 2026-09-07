import { expect, test } from '@playwright/test'

import { signIn, stubApi } from './fixtures/api-stub'

test.describe('Workout plan and logging', () => {
  test('generating a plan renders its days and exercises', async ({ page }) => {
    await stubApi(page)
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

    await expect(page).toHaveURL(/\/plan$/)
    await expect(
      page.getByRole('heading', { name: '3-Day Intermediate Muscle Building Plan' }),
    ).toBeVisible()
    // The first day starts expanded.
    await expect(page.getByText('Bench Press')).toBeVisible()
    await expect(page.getByText('Day 2')).toBeVisible()
  })

  test('logging a workout saves the values the user entered', async ({ page }) => {
    const api = await stubApi(page)
    await signIn(page)
    await page.goto('/plans')

    await page.getByRole('button', { name: /View Plan/ }).click()
    await expect(page).toHaveURL(/\/plan$/)

    await page.getByRole('button', { name: /Log This Workout/ }).first().click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()

    await dialog.getByLabel('Weight in kilograms for Bench Press').fill('82.5')
    await dialog.getByLabel('Reps completed for Bench Press').fill('6')
    await dialog.getByRole('button', { name: 'Save Session' }).click()

    await expect(page.getByText('Session logged!')).toBeVisible()

    const saved = api.savedSessions.at(-1) as {
      day_name: string
      exercise_logs: Array<{ exercise_name: string; reps_completed: number; weight_kg: number | null }>
    }
    expect(saved.day_name).toBe('Day 1')
    const bench = saved.exercise_logs.find((l) => l.exercise_name === 'Bench Press')!
    expect(bench.weight_kg).toBe(82.5)
    expect(bench.reps_completed).toBe(6)
  })

  test('a cleared required field blocks the save instead of sending zero', async ({ page }) => {
    const api = await stubApi(page)
    await signIn(page)
    await page.goto('/plans')
    await page.getByRole('button', { name: /View Plan/ }).click()
    await page.getByRole('button', { name: /Log This Workout/ }).first().click()

    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('Sets completed for Bench Press').fill('')
    await dialog.getByRole('button', { name: 'Save Session' }).click()

    await expect(dialog.getByRole('alert')).toContainText('Bench Press')
    expect(api.savedSessions).toHaveLength(0)
    // The modal stays open so the typed values are not lost.
    await expect(dialog).toBeVisible()
  })

  test('history lists saved plans and opens one', async ({ page }) => {
    await stubApi(page)
    await signIn(page)
    await page.goto('/plans')

    await expect(page.getByRole('heading', { name: 'My Plans' })).toBeVisible()
    await expect(page.getByText('1 plan generated')).toBeVisible()
    await expect(page.getByText('Build Muscle')).toBeVisible()

    await page.getByRole('button', { name: /View Plan/ }).click()
    await expect(
      page.getByRole('heading', { name: '3-Day Intermediate Muscle Building Plan' }),
    ).toBeVisible()
  })
})
