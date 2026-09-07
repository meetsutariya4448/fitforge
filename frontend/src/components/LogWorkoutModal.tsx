import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

import Button from './ui/Button'
import Toast from './Toast'
import { logWorkoutSession, toApiError } from '../services/api'
import { sessionCreateSchema, type Exercise, type WorkoutDay } from '../schemas/api'

/**
 * Modal for logging a completed workout session.
 */
export interface LogWorkoutModalProps {
  isOpen: boolean
  onClose: () => void
  /** The day being logged; null before the user picks one. */
  dayData: WorkoutDay | null
  /** ID of the parent workout plan, when the day came from a saved plan. */
  planId?: number | null
  /** Called after a session saves, so parents can refresh their data. */
  onSaved?: () => void
}

/**
 * A row as the user is editing it. Numeric fields are strings because that is
 * what an <input> holds — including the empty string when a field is cleared,
 * which Number() would silently turn into 0.
 */
interface LogRow {
  exercise_name: string
  sets_completed: string
  reps_completed: string
  weight_kg: string
}

const DEFAULT_SETS = 3
const DEFAULT_REPS = 10

/**
 * Seed a row from a planned exercise.
 *
 * `reps` arrives as free text ("8-12", "30 seconds"), so the leading number is
 * used as the starting value and the user adjusts from there.
 */
function toLogRow(exercise: Exercise): LogRow {
  const leadingNumber = exercise.reps ? Number.parseInt(exercise.reps, 10) : Number.NaN

  return {
    exercise_name: exercise.name,
    sets_completed: String(exercise.sets ?? DEFAULT_SETS),
    reps_completed: String(Number.isNaN(leadingNumber) ? DEFAULT_REPS : leadingNumber),
    weight_kg: '',
  }
}

function buildRows(exercises: Exercise[] | undefined): LogRow[] {
  return (exercises ?? []).map(toLogRow)
}

interface ToastState {
  message: string
  type: 'success' | 'error'
}

export default function LogWorkoutModal({
  isOpen,
  onClose,
  dayData,
  planId = null,
  onSaved,
}: LogWorkoutModalProps) {
  const [rows, setRows] = useState<LogRow[]>(() => buildRows(dayData?.exercises))
  const [notes, setNotes] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [toast, setToast] = useState<ToastState | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)

  // Reinitialise when the selected day changes (dayData is null on first render).
  useEffect(() => {
    setRows(buildRows(dayData?.exercises))
    setNotes('')
    setValidationError(null)
  }, [dayData])

  const updateRow = (index: number, field: keyof LogRow, value: string): void => {
    setRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    )
    setValidationError(null)
  }

  const handleSave = async (): Promise<void> => {
    // Validate before sending. An empty sets or reps field would otherwise reach
    // the API as 0 — accepted, and silently recorded as a workout of nothing.
    const candidate = {
      day_name: dayData?.day ?? 'Workout',
      plan_id: planId,
      notes: notes.trim() || null,
      exercise_logs: rows.map((row) => ({
        exercise_name: row.exercise_name,
        sets_completed: row.sets_completed === '' ? Number.NaN : Number(row.sets_completed),
        reps_completed: row.reps_completed === '' ? Number.NaN : Number(row.reps_completed),
        weight_kg: row.weight_kg === '' ? null : Number(row.weight_kg),
      })),
    }

    const parsed = sessionCreateSchema.safeParse(candidate)
    if (!parsed.success) {
      const issue = parsed.error.issues[0]
      const rowIndex = typeof issue?.path[1] === 'number' ? issue.path[1] : null
      const exerciseName = rowIndex !== null ? rows[rowIndex]?.exercise_name : null
      setValidationError(
        exerciseName
          ? `Check the numbers for ${exerciseName} — sets and reps are required.`
          : 'Please fill in sets and reps for every exercise.',
      )
      return
    }

    setIsSaving(true)
    setValidationError(null)
    try {
      await logWorkoutSession(parsed.data)
      setToast({ message: 'Session logged!', type: 'success' })
      onSaved?.()
      setTimeout(onClose, 1200) // brief pause so the user sees the toast
    } catch (error) {
      // Show what actually went wrong rather than a fixed string — "you are
      // offline" and "that plan no longer exists" call for different reactions.
      setToast({ message: toApiError(error).message, type: 'error' })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <>
      <AnimatePresence>
        {isOpen && (
          // ── Backdrop ──
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 flex items-center justify-center px-4"
            onClick={onClose}
          >
            {/* ── Modal card ── */}
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-label={dayData?.day ?? 'Log Workout'}
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              transition={{ duration: 0.2 }}
              className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-lg max-h-[90vh] flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 flex-shrink-0">
                <h2 className="font-bold text-white text-lg">{dayData?.day ?? 'Log Workout'}</h2>
                <button
                  type="button"
                  onClick={onClose}
                  aria-label="Close"
                  className="text-gray-500 hover:text-gray-300 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Exercise list — scrollable */}
              <div className="overflow-y-auto flex-1 px-6 py-4 space-y-5">
                {rows.map((row, i) => (
                  <div key={`${row.exercise_name}-${i}`} className="space-y-2">
                    <p className="font-semibold text-white text-sm">{row.exercise_name}</p>
                    <div className="grid grid-cols-3 gap-2">
                      <label className="block">
                        <span className="text-xs text-gray-500 mb-1 block">Sets</span>
                        <input
                          type="number"
                          min={1}
                          value={row.sets_completed}
                          onChange={(e) => updateRow(i, 'sets_completed', e.target.value)}
                          aria-label={`Sets completed for ${row.exercise_name}`}
                          className="input text-sm py-2"
                        />
                      </label>
                      <label className="block">
                        <span className="text-xs text-gray-500 mb-1 block">Reps</span>
                        <input
                          type="number"
                          min={1}
                          value={row.reps_completed}
                          onChange={(e) => updateRow(i, 'reps_completed', e.target.value)}
                          aria-label={`Reps completed for ${row.exercise_name}`}
                          className="input text-sm py-2"
                        />
                      </label>
                      <label className="block">
                        <span className="text-xs text-gray-500 mb-1 block">Weight (kg)</span>
                        <input
                          type="number"
                          min={0}
                          step={0.5}
                          value={row.weight_kg}
                          onChange={(e) => updateRow(i, 'weight_kg', e.target.value)}
                          placeholder="—"
                          aria-label={`Weight in kilograms for ${row.exercise_name}`}
                          className="input text-sm py-2"
                        />
                      </label>
                    </div>
                  </div>
                ))}

                {/* Notes */}
                <div>
                  <label htmlFor="session-notes" className="text-xs text-gray-500 mb-1 block">
                    Session notes <span className="text-gray-600">(optional)</span>
                  </label>
                  <textarea
                    id="session-notes"
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="How did it feel? Any adjustments?"
                    className="input resize-none text-sm"
                  />
                </div>
              </div>

              {/* Footer */}
              <div className="px-6 py-4 border-t border-gray-800 flex-shrink-0">
                {validationError && (
                  <p role="alert" className="text-sm text-red-400 mb-3">
                    {validationError}
                  </p>
                )}
                <div className="flex items-center justify-end gap-3">
                  <Button variant="ghost" size="sm" onClick={onClose} disabled={isSaving}>
                    Cancel
                  </Button>
                  <Button size="sm" onClick={handleSave} disabled={isSaving}>
                    {isSaving ? 'Saving…' : 'Save Session'}
                  </Button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toast rendered outside the modal so it survives modal close */}
      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />
      )}
    </>
  )
}
