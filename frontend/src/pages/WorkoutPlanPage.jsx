import { useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Dumbbell, ArrowLeft, RefreshCw, LayoutList, TrendingUp, LogOut, LogIn } from 'lucide-react'
import { motion } from 'framer-motion'
import WorkoutPlan from '../components/workout/WorkoutPlan'
import Button from '../components/ui/Button'
import LogWorkoutModal from '../components/LogWorkoutModal'

/**
 * Workout plan display page.
 * Reads the plan from router location state (set by Onboarding.jsx).
 * If state is missing (e.g. direct navigation), redirects to onboarding.
 */
export default function WorkoutPlanPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const plan = location.state?.plan
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedDay, setSelectedDay] = useState(null)
  const [isLoggedIn, setIsLoggedIn] = useState(() => !!localStorage.getItem('fitforge_token'))

  const handleLogout = () => {
    localStorage.removeItem('fitforge_token')
    setIsLoggedIn(false)
    navigate('/auth')
  }

  // Guard: redirect if there's no plan to display
  useEffect(() => {
    if (!plan) {
      navigate('/plans', { replace: true })
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
            <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard')}>
              <TrendingUp className="w-4 h-4 mr-1.5" />
              Dashboard
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate('/plans')}>
              <LayoutList className="w-4 h-4 mr-1.5" />
              My Plans
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
              <ArrowLeft className="w-4 h-4 mr-1.5" />
              Home
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

      {/* ── Plan content ── */}
      <motion.main
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="max-w-3xl mx-auto px-4 pt-10"
      >
        <WorkoutPlan
          plan={plan}
          onLogDay={(day) => { setSelectedDay(day); setModalOpen(true) }}
        />
      </motion.main>

      <LogWorkoutModal
        key={selectedDay?.day}
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        dayData={selectedDay}
        planId={null}
      />
    </div>
  )
}
