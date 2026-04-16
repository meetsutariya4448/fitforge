import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Dumbbell } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import OnboardingForm from '../components/onboarding/OnboardingForm'
import { generateWorkoutPlan } from '../services/api'

/**
 * Onboarding page — hosts the multi-step form and handles form submission.
 * On success, navigates to /plan passing the workout plan via router state.
 */
export default function Onboarding() {
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  // Auth guard — unauthenticated users must log in before generating a plan
  useEffect(() => {
    if (!localStorage.getItem('fitforge_token')) {
      navigate('/auth', { replace: true })
    }
  }, [navigate])

  /**
   * Called by OnboardingForm when all steps are completed.
   * @param {Object} formData - Collected onboarding data
   */
  const handleSubmit = async (formData) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await generateWorkoutPlan(formData)
      // Pass plan data to WorkoutPlanPage via router state
      navigate('/plan', { state: { plan: response.plan } })
    } catch (err) {
      const message = err.response?.data?.detail || 'Something went wrong. Please try again.'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center px-4 py-12">
      {/* Logo */}
      <div className="flex items-center gap-2 mb-10">
        <Dumbbell className="w-6 h-6 text-brand-500" />
        <span className="text-xl font-bold text-white">FitForge</span>
      </div>

      {/* Loading overlay */}
      <AnimatePresence>
        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-gray-950/80 backdrop-blur-sm z-50 flex flex-col items-center justify-center gap-4"
          >
            <div className="w-14 h-14 border-4 border-gray-700 border-t-brand-500 rounded-full animate-spin" />
            <p className="text-white font-medium text-lg">Building your personalised plan…</p>
            <p className="text-gray-400 text-sm">Claude AI is crafting your workout</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error banner */}
      {error && (
        <div className="mb-6 w-full max-w-lg bg-red-950/50 border border-red-800 text-red-300 rounded-xl px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <OnboardingForm onSubmit={handleSubmit} isLoading={isLoading} />
    </div>
  )
}
