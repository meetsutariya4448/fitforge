import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { motion } from 'framer-motion'

import Button from '../components/ui/Button'
import LogWorkoutModal from '../components/LogWorkoutModal'
import Navbar from '../components/Navbar'
import WorkoutPlan from '../components/workout/WorkoutPlan'
import {
  workoutPlanSchema,
  type WorkoutDay,
  type WorkoutPlan as WorkoutPlanData,
} from '../schemas/api'

/**
 * The plan arrives through router state, which survives a client-side
 * navigation but not a refresh or a pasted link — and is user-controllable, so
 * it is validated rather than trusted.
 */
function usePlanFromRouterState(): WorkoutPlanData | null {
  const location = useLocation()
  const raw = (location.state as { plan?: unknown } | null)?.plan
  if (raw === undefined) return null

  const parsed = workoutPlanSchema.safeParse(raw)
  return parsed.success ? parsed.data : null
}

export default function WorkoutPlanPage() {
  const navigate = useNavigate()
  const plan = usePlanFromRouterState()

  const [modalOpen, setModalOpen] = useState(false)
  const [selectedDay, setSelectedDay] = useState<WorkoutDay | null>(null)

  useEffect(() => {
    document.title = 'FitForge — Your Plan'
    if (!plan) navigate('/plans', { replace: true })
  }, [plan, navigate])

  if (!plan) return null

  return (
    <div className="min-h-screen bg-gray-950 pb-24">
      <Navbar />

      {/* Regenerate shortcut */}
      <div className="max-w-3xl mx-auto px-4 pt-6 flex justify-end">
        <Button variant="ghost" size="sm" onClick={() => navigate('/onboarding')}>
          <RefreshCw className="w-4 h-4 mr-1.5" />
          Regenerate Plan
        </Button>
      </div>

      <motion.main
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="max-w-3xl mx-auto px-4 pt-4"
      >
        <WorkoutPlan
          plan={plan}
          onLogDay={(day) => {
            setSelectedDay(day)
            setModalOpen(true)
          }}
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
