import { useState } from 'react'
import { ChevronDown, ChevronUp, Clock, Dumbbell } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

/**
 * Collapsible card for a single workout day.
 *
 * Shows day title and focus when collapsed; expands to reveal
 * all exercises, warmup/cooldown notes.
 *
 * @param {Object}  day           - WorkoutDay object from the API
 * @param {boolean} defaultOpen   - Whether to start expanded
 * @param {number}  index         - Used for staggered entrance animation
 */
export default function DayCard({ day, defaultOpen = false, index = 0 }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.07 }}
      className="card overflow-hidden"
    >
      {/* ── Header (always visible, click to toggle) ── */}
      <button
        onClick={() => setIsOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-800/50 transition-colors"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-4">
          {/* Day number pill */}
          <span className="w-10 h-10 rounded-xl bg-brand-500/15 text-brand-400 font-bold text-sm flex items-center justify-center flex-shrink-0">
            {day.day.replace(/\D/g, '') || index + 1}
          </span>

          <div className="text-left">
            <div className="font-semibold text-white text-sm">{day.day}</div>
            <div className="text-gray-400 text-xs mt-0.5">{day.focus}</div>
          </div>
        </div>

        <div className="flex items-center gap-4 text-gray-500">
          {/* Duration */}
          <span className="hidden sm:flex items-center gap-1.5 text-xs">
            <Clock className="w-3.5 h-3.5" />
            {day.duration_minutes} min
          </span>
          {/* Exercise count */}
          <span className="hidden sm:flex items-center gap-1.5 text-xs">
            <Dumbbell className="w-3.5 h-3.5" />
            {day.exercises.length} exercises
          </span>
          {/* Expand icon */}
          <span className="text-gray-600">
            {isOpen ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </span>
        </div>
      </button>

      {/* ── Expanded content ── */}
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 border-t border-gray-800">
              {/* Warmup */}
              {day.warmup_notes && (
                <div className="mt-4 px-4 py-3 bg-blue-950/30 border border-blue-900/40 rounded-xl text-sm text-blue-300">
                  <span className="font-semibold text-blue-400">Warm-up: </span>
                  {day.warmup_notes}
                </div>
              )}

              {/* Exercise table */}
              <div className="mt-4 space-y-2">
                {day.exercises.map((exercise, i) => (
                  <ExerciseRow key={i} exercise={exercise} index={i} />
                ))}
              </div>

              {/* Cooldown */}
              {day.cooldown_notes && (
                <div className="mt-4 px-4 py-3 bg-purple-950/30 border border-purple-900/40 rounded-xl text-sm text-purple-300">
                  <span className="font-semibold text-purple-400">Cool-down: </span>
                  {day.cooldown_notes}
                </div>
              )}

              {/* Mobile stats */}
              <div className="mt-4 flex gap-4 text-xs text-gray-500 sm:hidden">
                <span className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" /> {day.duration_minutes} min
                </span>
                <span className="flex items-center gap-1">
                  <Dumbbell className="w-3.5 h-3.5" /> {day.exercises.length} exercises
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

/**
 * A single row in the exercise list.
 */
function ExerciseRow({ exercise, index }) {
  return (
    <div className="flex items-start gap-3 px-3 py-3 rounded-xl bg-gray-800/40 hover:bg-gray-800/70 transition-colors">
      {/* Index number */}
      <span className="w-6 h-6 rounded-md bg-gray-700 text-gray-400 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
        {index + 1}
      </span>

      <div className="flex-1 min-w-0">
        <div className="font-medium text-white text-sm">{exercise.name}</div>

        {/* Sets / reps / rest in a compact row */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1">
          {exercise.sets != null && (
            <span className="text-xs text-gray-400">
              <span className="text-gray-500">Sets </span>{exercise.sets}
            </span>
          )}
          {exercise.reps && (
            <span className="text-xs text-gray-400">
              <span className="text-gray-500">Reps </span>{exercise.reps}
            </span>
          )}
          {exercise.rest_seconds != null && (
            <span className="text-xs text-gray-400">
              <span className="text-gray-500">Rest </span>{exercise.rest_seconds}s
            </span>
          )}
        </div>

        {/* Form tip */}
        {exercise.notes && (
          <p className="text-xs text-gray-500 mt-1.5 italic">{exercise.notes}</p>
        )}
      </div>
    </div>
  )
}
