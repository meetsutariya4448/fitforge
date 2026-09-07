import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Dumbbell,
  Calendar,
  Target,
  BarChart2,
  Clock,
  ArrowRight,
  Plus,
  AlertTriangle,
} from 'lucide-react'
import { motion } from 'framer-motion'

import Button from '../components/ui/Button'
import Navbar from '../components/Navbar'
import { getWorkoutHistory, toApiError } from '../services/api'
import {
  workoutPlanSchema,
  type WorkoutPlan,
  type WorkoutPlanHistoryItem,
} from '../schemas/api'

// ── Formatting helpers ────────────────────────────────────────────────────────

/** Convert a snake_case enum string to Title Case: "build_muscle" → "Build Muscle". */
function formatLabel(value: string): string {
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

/** Format an ISO date string as "Apr 1, 2026". */
function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// ── Subcomponents ─────────────────────────────────────────────────────────────

/**
 * A single plan card in the history grid.
 *
 * `plan_json` is a stored blob, possibly written by an older version of the app,
 * so it is parsed rather than assumed. A row that no longer matches the current
 * plan shape renders as an unopenable card instead of taking the whole page down
 * with it — one bad historical row should not cost the user the other nine.
 */
function PlanCard({ plan, index }: { plan: WorkoutPlanHistoryItem; index: number }) {
  const navigate = useNavigate()
  const parsed = workoutPlanSchema.safeParse(plan.plan_json)
  const planData: WorkoutPlan | null = parsed.success ? parsed.data : null

  const handleViewPlan = (): void => {
    // WorkoutPlanPage reads location.state.plan, so this matches the shape the
    // onboarding flow sets.
    navigate('/plan', { state: { plan: planData } })
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.07 }}
      className="card p-5 flex flex-col gap-4 hover:border-gray-700 transition-colors"
    >
      {/* ── Plan title ── */}
      <div>
        <h3 className="font-semibold text-white text-base leading-snug line-clamp-2">
          {planData?.title ?? 'Unavailable plan'}
        </h3>
      </div>

      {/* ── Metadata pills ── */}
      <div className="flex flex-wrap gap-2">
        <MetaPill icon={<Target className="w-3.5 h-3.5" />} label={formatLabel(plan.goal)} />
        <MetaPill
          icon={<BarChart2 className="w-3.5 h-3.5" />}
          label={formatLabel(plan.fitness_level)}
        />
        <MetaPill
          icon={<Clock className="w-3.5 h-3.5" />}
          label={`${plan.days_per_week} day${plan.days_per_week !== 1 ? 's' : ''} / week`}
        />
      </div>

      {!planData && (
        <p className="flex items-start gap-2 text-xs text-amber-400">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          This plan was saved in an older format and can no longer be opened.
        </p>
      )}

      {/* ── Footer: date + action ── */}
      <div className="flex items-center justify-between mt-auto pt-3 border-t border-gray-800">
        <span className="flex items-center gap-1.5 text-xs text-gray-500">
          <Calendar className="w-3.5 h-3.5" />
          {formatDate(plan.created_at)}
        </span>
        <Button size="sm" onClick={handleViewPlan} disabled={!planData}>
          View Plan
          <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
        </Button>
      </div>
    </motion.div>
  )
}

/** Small icon + text pill used in the plan card metadata row. */
function MetaPill({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 bg-gray-800 text-gray-400 text-xs px-2.5 py-1 rounded-lg">
      {icon}
      {label}
    </span>
  )
}

/** Full-page loading spinner, matching the style used in Onboarding. */
function LoadingState() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex-1 flex flex-col items-center justify-center gap-4 py-32"
    >
      <div
        aria-hidden="true"
        className="w-10 h-10 border-4 border-gray-700 border-t-brand-500 rounded-full animate-spin"
      />
      <p className="text-gray-400 text-sm">Loading your plans…</p>
    </div>
  )
}

/** Empty state shown when the user has no saved plans yet. */
function EmptyState() {
  const navigate = useNavigate()
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex-1 flex flex-col items-center justify-center py-32 text-center px-4"
    >
      <div className="w-16 h-16 bg-gray-800 rounded-2xl flex items-center justify-center mb-6">
        <Dumbbell className="w-8 h-8 text-gray-600" />
      </div>
      <h2 className="text-xl font-semibold text-white mb-2">No plans yet</h2>
      <p className="text-gray-400 text-sm mb-8 max-w-xs">
        Generate your first AI-powered workout plan and it will appear here.
      </p>
      <Button onClick={() => navigate('/onboarding')}>
        <Plus className="w-4 h-4 mr-2" />
        Create My First Plan
      </Button>
    </motion.div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

/**
 * My Plans history page — shows all saved workout plans for the current user.
 *
 * The auth guard now lives in RequireAuth (App.tsx) rather than a local
 * useEffect redirect.
 */
export default function PlansHistory() {
  const navigate = useNavigate()
  const [plans, setPlans] = useState<WorkoutPlanHistoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'FitForge — My Plans'

    let cancelled = false

    getWorkoutHistory()
      .then((history) => {
        if (cancelled) return
        setPlans(history.plans)
        setTotal(history.total)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const apiError = toApiError(err)
        // A 401 means the interceptor is already redirecting to /auth; showing
        // an error under a page that is about to unmount just adds noise.
        if (apiError.status !== 401) setError(apiError.message)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      <Navbar />

      <div className="max-w-5xl mx-auto w-full px-4 sm:px-6 pt-10 pb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white mb-1">My Plans</h1>
          {!isLoading && total > 0 && (
            <p className="text-gray-400 text-sm">
              {total} plan{total !== 1 ? 's' : ''} generated
            </p>
          )}
        </div>
        <Button size="sm" onClick={() => navigate('/onboarding')}>
          <Plus className="w-4 h-4 mr-1.5" /> New Plan
        </Button>
      </div>

      {error && (
        <div className="max-w-5xl mx-auto w-full px-4 sm:px-6 mb-4">
          <div
            role="alert"
            className="bg-red-950/50 border border-red-800 text-red-300 rounded-xl px-4 py-3 text-sm"
          >
            {error}
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto w-full px-4 sm:px-6 pb-24 flex flex-col flex-1">
        {isLoading ? (
          <LoadingState />
        ) : total === 0 ? (
          <EmptyState />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {plans.map((plan, index) => (
              <PlanCard key={plan.id} plan={plan} index={index} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
