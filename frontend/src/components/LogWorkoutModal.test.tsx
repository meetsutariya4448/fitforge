/**
 * Tests for the workout-logging modal.
 *
 * The behaviour worth pinning here is the validation added during the
 * TypeScript migration: cleared number fields used to reach the API as 0, so a
 * user who blanked a field recorded a session of zero sets and zero reps — a
 * silent data-quality bug that looked like a successful save.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LogWorkoutModal from './LogWorkoutModal'
import { ApiError } from '../services/api'
import type { WorkoutDay } from '../schemas/api'

const { logWorkoutSession } = vi.hoisted(() => ({ logWorkoutSession: vi.fn() }))

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>()
  return { ...actual, logWorkoutSession }
})

const DAY: WorkoutDay = {
  day: 'Day 1',
  focus: 'Upper Body',
  duration_minutes: 45,
  exercises: [
    { name: 'Bench Press', sets: 4, reps: '8-10', rest_seconds: 90, notes: null },
    { name: 'Pull Up', sets: 3, reps: '30 seconds', rest_seconds: 60, notes: null },
  ],
  warmup_notes: null,
  cooldown_notes: null,
}

function renderModal(overrides: Partial<React.ComponentProps<typeof LogWorkoutModal>> = {}) {
  const onClose = vi.fn()
  const utils = render(
    <LogWorkoutModal isOpen onClose={onClose} dayData={DAY} planId={7} {...overrides} />,
  )
  return { onClose, ...utils }
}

beforeEach(() => {
  logWorkoutSession.mockReset()
})

describe('LogWorkoutModal', () => {
  it('prefills each exercise from the plan', () => {
    renderModal()

    expect(screen.getByText('Bench Press')).toBeInTheDocument()
    expect(screen.getByLabelText('Sets completed for Bench Press')).toHaveValue(4)
    // "8-10" is free text; the leading number seeds the field.
    expect(screen.getByLabelText('Reps completed for Bench Press')).toHaveValue(8)
    expect(screen.getByLabelText('Seconds completed for Pull Up')).toHaveValue(30)
    expect(screen.queryByLabelText('Reps completed for Pull Up')).not.toBeInTheDocument()
  })

  it('recognizes time units even when the plan says hold for minutes', () => {
    renderModal({ dayData: { ...DAY, exercises: [{
      name: 'Wall Sit', sets: 2, reps: 'Hold for 2 minutes', rest_seconds: 60, notes: null,
    }] } })
    expect(screen.getByLabelText('Seconds completed for Wall Sit')).toHaveValue(120)
  })

  it('submits the edited values with the plan id', async () => {
    const user = userEvent.setup()
    logWorkoutSession.mockResolvedValue({})
    renderModal()

    const weight = screen.getByLabelText('Weight in kilograms for Bench Press')
    await user.type(weight, '82.5')
    await user.click(screen.getByRole('button', { name: 'Save Session' }))

    await waitFor(() => expect(logWorkoutSession).toHaveBeenCalledTimes(1))
    expect(logWorkoutSession).toHaveBeenCalledWith(
      expect.objectContaining({
        day_name: 'Day 1',
        plan_id: 7,
        exercise_logs: expect.arrayContaining([
          expect.objectContaining({ exercise_name: 'Bench Press', weight_kg: 82.5 }),
        ]),
      }),
    )
    const payload = logWorkoutSession.mock.calls[0]![0]
    expect(payload.exercise_logs[1]).toMatchObject({
      exercise_name: 'Pull Up', reps_completed: null, duration_seconds: 30,
    })
  })

  it('leaves weight null when it is not filled in', async () => {
    const user = userEvent.setup()
    logWorkoutSession.mockResolvedValue({})
    renderModal()

    await user.click(screen.getByRole('button', { name: 'Save Session' }))

    await waitFor(() => expect(logWorkoutSession).toHaveBeenCalled())
    const payload = logWorkoutSession.mock.calls[0]![0]
    // Bodyweight exercises are logged without a weight; 0 kg would be a lie
    // that then pollutes the volume charts and personal records.
    expect(payload.exercise_logs[0].weight_kg).toBeNull()
  })

  it('refuses to save when a required number has been cleared', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.clear(screen.getByLabelText('Sets completed for Bench Press'))
    await user.click(screen.getByRole('button', { name: 'Save Session' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/Bench Press/)
    // The request must not go out at all — this used to send sets_completed: 0.
    expect(logWorkoutSession).not.toHaveBeenCalled()
  })

  it('refuses to save a timed exercise with missing seconds', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.clear(screen.getByLabelText('Seconds completed for Pull Up'))
    await user.click(screen.getByRole('button', { name: 'Save Session' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/Pull Up.*seconds/)
    expect(logWorkoutSession).not.toHaveBeenCalled()
  })

  it('clears the validation message once the field is corrected', async () => {
    const user = userEvent.setup()
    logWorkoutSession.mockResolvedValue({})
    renderModal()

    const sets = screen.getByLabelText('Sets completed for Bench Press')
    await user.clear(sets)
    await user.click(screen.getByRole('button', { name: 'Save Session' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()

    await user.type(sets, '3')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows the reason a save failed rather than a fixed string', async () => {
    const user = userEvent.setup()
    logWorkoutSession.mockRejectedValue(
      new ApiError('NETWORK_ERROR', 'Could not reach the server. Check your connection and try again.', null),
    )
    renderModal()

    await user.click(screen.getByRole('button', { name: 'Save Session' }))

    // "Failed to save — try again" gave the user nothing to act on; being
    // offline and having a stale plan call for different responses.
    expect(await screen.findByText(/could not reach the server/i)).toBeInTheDocument()
  })

  it('does not close the modal when saving fails', async () => {
    const user = userEvent.setup()
    logWorkoutSession.mockRejectedValue(new ApiError('HTTP_500', 'Server error.', 500))
    const { onClose } = renderModal()

    await user.click(screen.getByRole('button', { name: 'Save Session' }))

    await screen.findByText('Server error.')
    // Closing would discard everything the user typed.
    expect(onClose).not.toHaveBeenCalled()
  })

  it('renders nothing but stays mounted when closed', () => {
    render(<LogWorkoutModal isOpen={false} onClose={vi.fn()} dayData={DAY} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
