/**
 * Tests for the onboarding wizard's gating and final validation.
 *
 * Two behaviours matter here. Each step must refuse to advance until it is
 * satisfied, and the last step must validate the whole draft against the same
 * schema the API client uses — the per-step checks are UI affordances, and a
 * user can reach the end and then clear a field.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import OnboardingForm from './OnboardingForm'

function setup() {
  const onSubmit = vi.fn()
  render(<OnboardingForm onSubmit={onSubmit} />)
  return { user: userEvent.setup(), onSubmit }
}

const continueButton = () => screen.getByRole('button', { name: 'Continue' })

type User = ReturnType<typeof userEvent.setup>

/**
 * Advance a step and wait for the next one.
 *
 * The wizard animates steps with AnimatePresence mode="wait", so the outgoing
 * step must finish exiting before the incoming one mounts — the transition is
 * never synchronous with the click.
 */
async function advanceTo(user: User, heading: string | RegExp) {
  await user.click(continueButton())
  await screen.findByText(heading)
}

/** Fill step 1 and advance to the goal step. */
async function completeStep1(user: User) {
  await user.type(screen.getByLabelText('First name'), 'Alex')
  await user.type(screen.getByLabelText('Age'), '28')
  await advanceTo(user, "What's your primary goal?")
}

/** Walk from the goal step through to the final schedule step. */
async function completeToLastStep(user: User) {
  await user.click(screen.getByRole('radio', { name: /Build Muscle/ }))
  await advanceTo(user, 'Your fitness level?')
  await user.click(screen.getByRole('radio', { name: /Intermediate/ }))
  await advanceTo(user, 'What equipment do you have?')
  await user.click(screen.getByRole('checkbox', { name: /Dumbbells/ }))
  await advanceTo(user, 'How many days per week?')
}

describe('OnboardingForm', () => {
  it('blocks the first step until name and age are valid', async () => {
    const { user } = setup()

    expect(continueButton()).toBeDisabled()

    await user.type(screen.getByLabelText('First name'), 'Alex')
    expect(continueButton()).toBeDisabled()

    // Under the minimum age — the backend would reject this with a 422.
    await user.type(screen.getByLabelText('Age'), '11')
    expect(continueButton()).toBeDisabled()

    await user.clear(screen.getByLabelText('Age'))
    await user.type(screen.getByLabelText('Age'), '28')
    expect(continueButton()).toBeEnabled()
  })

  it('treats a cleared age as incomplete rather than as zero', async () => {
    const { user } = setup()

    await user.type(screen.getByLabelText('First name'), 'Alex')
    await user.type(screen.getByLabelText('Age'), '28')
    expect(continueButton()).toBeEnabled()

    await user.clear(screen.getByLabelText('Age'))
    // Number('') is 0, which would look like a filled-in field holding a
    // nonsense age.
    expect(continueButton()).toBeDisabled()
  })

  it('gates every subsequent step on its own answer', async () => {
    const { user } = setup()
    await completeStep1(user)

    expect(continueButton()).toBeDisabled()
    await user.click(screen.getByRole('radio', { name: /Build Muscle/ }))
    expect(continueButton()).toBeEnabled()
    await advanceTo(user, 'Your fitness level?')

    expect(continueButton()).toBeDisabled()
    await user.click(screen.getByRole('radio', { name: /Intermediate/ }))
    await advanceTo(user, 'What equipment do you have?')

    expect(continueButton()).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: /Dumbbells/ }))
    await advanceTo(user, 'How many days per week?')

    // Days per week defaults to 3, so the last step starts satisfied.
    expect(screen.getByRole('button', { name: 'Generate My Plan' })).toBeEnabled()
  })

  it('submits a validated payload, not the raw draft', async () => {
    const { user, onSubmit } = setup()

    await completeStep1(user)
    await completeToLastStep(user)
    await user.click(screen.getByRole('button', { name: 'Generate My Plan' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith({
      name: 'Alex',
      age: 28,
      fitness_goal: 'build_muscle',
      fitness_level: 'intermediate',
      available_equipment: ['dumbbells'],
      days_per_week: 3,
      // Trimmed to null rather than sent as an empty string.
      additional_notes: null,
      session_history: undefined,
    })
  })

  it('keeps answers when stepping backwards', async () => {
    const { user } = setup()

    await completeStep1(user)
    await user.click(screen.getByRole('radio', { name: /Build Muscle/ }))
    await user.click(screen.getByRole('button', { name: /Back/ }))

    expect(await screen.findByLabelText('First name')).toHaveValue('Alex')
    expect(screen.getByLabelText('Age')).toHaveValue(28)
  })

  it('makes "No Equipment" mutually exclusive with real equipment', async () => {
    const { user } = setup()

    await completeStep1(user)
    await user.click(screen.getByRole('radio', { name: /Build Muscle/ }))
    await advanceTo(user, 'Your fitness level?')
    await user.click(screen.getByRole('radio', { name: /Intermediate/ }))
    await advanceTo(user, 'What equipment do you have?')

    const noEquipment = screen.getByRole('checkbox', { name: /No Equipment/ })
    const dumbbells = screen.getByRole('checkbox', { name: /Dumbbells/ })

    await user.click(dumbbells)
    await user.click(noEquipment)
    // "I have dumbbells and also no equipment" is not a coherent answer.
    expect(dumbbells).toHaveAttribute('aria-checked', 'false')
    expect(noEquipment).toHaveAttribute('aria-checked', 'true')

    await user.click(dumbbells)
    expect(noEquipment).toHaveAttribute('aria-checked', 'false')
  })
})
