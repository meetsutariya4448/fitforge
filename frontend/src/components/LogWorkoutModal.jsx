import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Button from './ui/Button'
import Toast from './Toast'
import { logWorkoutSession } from '../services/api'

/**
 * Modal for logging a completed workout session.
 *
 * @param {boolean}  isOpen   - Controls visibility
 * @param {Function} onClose  - Called when the modal should close
 * @param {Object}   dayData  - The WorkoutDay object from plan_json (has .day, .exercises[])
 * @param {number}   planId   - ID of the parent workout plan (may be null)
 */
export default function LogWorkoutModal({ isOpen, onClose, dayData, planId }) {
  const buildLogs = (exercises) =>
    (exercises || []).map((ex) => ({
      exercise_name: ex.name,
      sets_completed: ex.sets ?? 3,
      reps_completed: typeof ex.reps === 'number' ? ex.reps : parseInt(ex.reps, 10) || 10,
      weight_kg: '',
    }))

  const [logs, setLogs] = useState(() => buildLogs(dayData?.exercises))
  const [notes, setNotes] = useState('')

  // Reinitialize when the selected day changes (dayData is null on first render)
  useEffect(() => {
    setLogs(buildLogs(dayData?.exercises))
    setNotes('')
  }, [dayData])
  const [isSaving, setIsSaving] = useState(false)
  const [toast, setToast] = useState(null)   // { message, type }

  const updateLog = (index, field, value) => {
    setLogs((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], [field]: value }
      return next
    })
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await logWorkoutSession({
        day_name: dayData?.day ?? 'Workout',
        plan_id: planId ?? null,
        notes: notes.trim() || null,
        exercise_logs: logs.map((l) => ({
          exercise_name: l.exercise_name,
          sets_completed: Number(l.sets_completed),
          reps_completed: Number(l.reps_completed),
          weight_kg: l.weight_kg !== '' ? Number(l.weight_kg) : null,
        })),
      })
      setToast({ message: 'Session logged!', type: 'success' })
      setTimeout(onClose, 1200)   // brief pause so user sees the toast
    } catch {
      setToast({ message: 'Failed to save — try again', type: 'error' })
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
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              transition={{ duration: 0.2 }}
              className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-lg max-h-[90vh] flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 flex-shrink-0">
                <h2 className="font-bold text-white text-lg">
                  {dayData?.day ?? 'Log Workout'}
                </h2>
                <button
                  onClick={onClose}
                  className="text-gray-500 hover:text-gray-300 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Exercise list — scrollable */}
              <div className="overflow-y-auto flex-1 px-6 py-4 space-y-5">
                {logs.map((log, i) => (
                  <div key={i} className="space-y-2">
                    <p className="font-semibold text-white text-sm">{log.exercise_name}</p>
                    <div className="grid grid-cols-3 gap-2">
                      <label className="block">
                        <span className="text-xs text-gray-500 mb-1 block">Sets</span>
                        <input
                          type="number"
                          min={1}
                          value={log.sets_completed}
                          onChange={(e) => updateLog(i, 'sets_completed', e.target.value)}
                          className="input text-sm py-2"
                        />
                      </label>
                      <label className="block">
                        <span className="text-xs text-gray-500 mb-1 block">Reps</span>
                        <input
                          type="number"
                          min={1}
                          value={log.reps_completed}
                          onChange={(e) => updateLog(i, 'reps_completed', e.target.value)}
                          className="input text-sm py-2"
                        />
                      </label>
                      <label className="block">
                        <span className="text-xs text-gray-500 mb-1 block">Weight (kg)</span>
                        <input
                          type="number"
                          min={0}
                          step={0.5}
                          value={log.weight_kg}
                          onChange={(e) => updateLog(i, 'weight_kg', e.target.value)}
                          placeholder="—"
                          className="input text-sm py-2"
                        />
                      </label>
                    </div>
                  </div>
                ))}

                {/* Notes */}
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">
                    Session notes <span className="text-gray-600">(optional)</span>
                  </label>
                  <textarea
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="How did it feel? Any adjustments?"
                    className="input resize-none text-sm"
                  />
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-800 flex-shrink-0">
                <Button variant="ghost" size="sm" onClick={onClose} disabled={isSaving}>
                  Cancel
                </Button>
                <Button size="sm" onClick={handleSave} disabled={isSaving}>
                  {isSaving ? 'Saving…' : 'Save Session'}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toast rendered outside the modal so it survives modal close */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </>
  )
}
