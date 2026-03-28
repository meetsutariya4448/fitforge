import { useLocation, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { Dumbbell, ArrowLeft, RefreshCw } from 'lucide-react'
import { motion } from 'framer-motion'
import WorkoutPlan from '../components/workout/WorkoutPlan'
import Button from '../components/ui/Button'

/**
 * Workout plan display page.
 * Reads the plan from router location state (set by Onboarding.jsx).
 * If state is missing (e.g. direct navigation), redirects to onboarding.
 */
export default function WorkoutPlanPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const plan = location.state?.plan

  // Guard: redirect if there's no plan to display
  useEffect(() => {
    if (!plan) {
      navigate('/onboarding', { replace: true })
    }
  }, [plan, navigate])

  if (!plan) return null

  return (
    <div className="min-h-screen bg-gray-950 pb-24">
      {/* ── Top bar ── */}
      <nav className="border-b border-gray-800 px-6 py-4 sticky top-0 bg-gray-950/90 backdrop-blur-sm z-10">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Dumbbell className="w-5 h-5 text-brand-500" />
            <span className="text-lg font-bold text-white">FitForge</span>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate('/onboarding')}>
              <RefreshCw className="w-4 h-4 mr-1.5" />
              Regenerate
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
              <ArrowLeft className="w-4 h-4 mr-1.5" />
              Home
            </Button>
          </div>
        </div>
      </nav>

      {/* ── Plan content ── */}
      <motion.main
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="max-w-3xl mx-auto px-4 pt-10"
      >
        <WorkoutPlan plan={plan} />
      </motion.main>
    </div>
  )
}
