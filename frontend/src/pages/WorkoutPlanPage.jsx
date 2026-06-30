import { useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { motion } from 'framer-motion'
import WorkoutPlan from '../components/workout/WorkoutPlan'
import Button from '../components/ui/Button'
import LogWorkoutModal from '../components/LogWorkoutModal'
import Navbar from '../components/Navbar'

export default function WorkoutPlanPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const plan = location.state?.plan
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedDay, setSelectedDay] = useState(null)

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
