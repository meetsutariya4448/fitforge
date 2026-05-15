import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Dumbbell, Calendar, Target, BarChart2, Clock, ArrowRight, Plus, TrendingUp, LogOut, LogIn } from 'lucide-react'
import { motion } from 'framer-motion'
import Button from '../components/ui/Button'
import { getWorkoutHistory } from '../services/api'

// ── Formatting helpers ────────────────────────────────────────────────────────

/**
 * Convert a snake_case enum string to Title Case.
 * e.g. "build_muscle" → "Build Muscle"
 */
function formatLabel(value) {
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

/**
 * Format an ISO date string as "Apr 1, 2026".
 */
function formatDate(isoString) {
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
 * @param {Object} plan   - History item from the API
 * @param {number} index  - Used for staggered entrance animation
 */
function PlanCard({ plan, index }) {
  const navigate = useNavigate()

  const handleViewPlan = () => {
    // Pass plan_json as router state — WorkoutPlanPage reads location.state.plan,
    // so this is identical to the shape set by the onboarding flow.
    navigate('/plan', { state: { plan: plan.plan_json } })
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
          {plan.plan_json.title}
        </h3>
      </div>

      {/* ── Metadata pills ── */}
      <div className="flex flex-wrap gap-2">
        <MetaPill icon={<Target className="w-3.5 h-3.5" />} label={formatLabel(plan.goal)} />
        <MetaPill icon={<BarChart2 className="w-3.5 h-3.5" />} label={formatLabel(plan.fitness_level)} />
        <MetaPill
          icon={<Clock className="w-3.5 h-3.5" />}
          label={`${plan.days_per_week} day${plan.days_per_week !== 1 ? 's' : ''} / week`}
        />
      </div>

      {/* ── Footer: date + action ── */}
      <div className="flex items-center justify-between mt-auto pt-3 border-t border-gray-800">
        <span className="flex items-center gap-1.5 text-xs text-gray-500">
          <Calendar className="w-3.5 h-3.5" />
          {formatDate(plan.created_at)}
        </span>
        <Button size="sm" onClick={handleViewPlan}>
          View Plan
          <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
        </Button>
      </div>
    </motion.div>
  )
}

/** Small icon + text pill used in the plan card metadata row. */
function MetaPill({ icon, label }) {
  return (
    <span className="inline-flex items-center gap-1.5 bg-gray-800 text-gray-400 text-xs px-2.5 py-1 rounded-lg">
      {icon}
      {label}
    </span>
  )
}

/** Full-page loading spinner, matches the style used in Onboarding.jsx. */
function LoadingState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 py-32">
      <div className="w-10 h-10 border-4 border-gray-700 border-t-brand-500 rounded-full animate-spin" />
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
 * Auth guard: if no JWT is found in localStorage, redirect to / immediately.
 * The Axios interceptor handles token expiry (clears localStorage on 401),
 * so a missing token here means the user is not logged in.
 */
export default function PlansHistory() {
  const navigate = useNavigate()
  const [plans, setPlans] = useState([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [isLoggedIn, setIsLoggedIn] = useState(() => !!localStorage.getItem('fitforge_token'))

  const handleLogout = () => {
    localStorage.removeItem('fitforge_token')
    setIsLoggedIn(false)
    navigate('/auth')
  }

  useEffect(() => {
    // Auth guard — redirect unauthenticated visitors before making any API call
    const token = localStorage.getItem('fitforge_token')
    if (!token) {
      navigate('/auth', { replace: true })
      return
    }

    getWorkoutHistory()
      .then(({ plans, total }) => {
        setPlans(plans)
        setTotal(total)
      })
      .catch((err) => {
        // 401 is handled globally (token cleared); other errors show a banner
        if (err.response?.status !== 401) {
          setError('Could not load your plans. Please try again.')
        }
      })
      .finally(() => setIsLoading(false))
  }, [navigate])

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* ── Navbar ── */}
      <nav className="border-b border-gray-800 px-6 py-4 sticky top-0 bg-gray-950/90 backdrop-blur-sm z-10">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div
            className="flex items-center gap-2 cursor-pointer"
            onClick={() => navigate('/')}
          >
            <Dumbbell className="w-5 h-5 text-brand-500" />
            <span className="text-lg font-bold text-white">FitForge</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard')}>
              <TrendingUp className="w-4 h-4 mr-1.5" />
              Dashboard
            </Button>
            <span className="text-sm font-semibold text-brand-400 flex items-center gap-1.5 px-3 py-1.5">
              <LayoutList className="w-4 h-4" />
              My Plans
            </span>
            <Button size="sm" onClick={() => navigate('/onboarding')}>
              <Plus className="w-4 h-4 mr-1.5" />
              New Plan
            </Button>
            {isLoggedIn ? (
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="w-4 h-4 mr-1.5" />
                Logout
              </Button>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => navigate('/auth')}>
                <LogIn className="w-4 h-4 mr-1.5" />
                Login
              </Button>
            )}
          </div>
        </div>
      </nav>

      {/* ── Page header ── */}
      <div className="max-w-5xl mx-auto w-full px-6 pt-10 pb-6">
        <h1 className="text-3xl font-extrabold text-white mb-1">My Plans</h1>
        {!isLoading && total > 0 && (
          <p className="text-gray-400 text-sm">
            {total} plan{total !== 1 ? 's' : ''} generated
          </p>
        )}
      </div>

      {/* ── Error banner ── */}
      {error && (
        <div className="max-w-5xl mx-auto w-full px-6 mb-4">
          <div className="bg-red-950/50 border border-red-800 text-red-300 rounded-xl px-4 py-3 text-sm">
            {error}
          </div>
        </div>
      )}

      {/* ── Content ── */}
      <div className="max-w-5xl mx-auto w-full px-6 pb-24 flex flex-col flex-1">
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
