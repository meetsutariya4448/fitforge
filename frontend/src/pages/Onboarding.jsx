import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Navbar from '../components/Navbar'
import OnboardingForm from '../components/onboarding/OnboardingForm'
import { generateWorkoutPlan } from '../services/api'

export default function Onboarding() {
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    document.title = 'FitForge — Build Your Plan'
    if (!localStorage.getItem('fitforge_token')) {
      navigate('/auth', { replace: true })
    }
  }, [navigate])

  const handleSubmit = async (formData) => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await generateWorkoutPlan(formData)
      navigate('/plan', { state: { plan: response.plan } })
    } catch (err) {
      const message = err.response?.data?.detail || 'Something went wrong. Please try again.'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      <Navbar />

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
            <p className="text-gray-400 text-sm">Groq AI is crafting your workout</p>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex-1 flex flex-col items-center justify-center px-4 py-12">
        {error && (
          <div className="mb-6 w-full max-w-lg bg-red-950/50 border border-red-800 text-red-300 rounded-xl px-4 py-3 text-sm">
            {error}
          </div>
        )}
        <OnboardingForm onSubmit={handleSubmit} isLoading={isLoading} />
      </div>
    </div>
  )
}
