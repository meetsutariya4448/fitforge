import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'

import Navbar from '../components/Navbar'
import OnboardingForm from '../components/onboarding/OnboardingForm'
import { generateWorkoutPlan, toApiError } from '../services/api'
import type { OnboardingData } from '../schemas/api'

export default function Onboarding() {
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'FitForge — Build Your Plan'
  }, [])
  // The auth check that used to live here is now RequireAuth in App.tsx.

  const handleSubmit = async (formData: OnboardingData): Promise<void> => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await generateWorkoutPlan(formData)
      navigate('/plan', { state: { plan: response.plan } })
    } catch (err) {
      setError(toApiError(err).message)
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
            role="status"
            aria-live="polite"
            className="fixed inset-0 bg-gray-950/80 backdrop-blur-sm z-50 flex flex-col items-center justify-center gap-4"
          >
            <div
              aria-hidden="true"
              className="w-14 h-14 border-4 border-gray-700 border-t-brand-500 rounded-full animate-spin"
            />
            <p className="text-white font-medium text-lg">Building your personalised plan…</p>
            <p className="text-gray-400 text-sm">Groq AI is crafting your workout</p>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex-1 flex flex-col items-center justify-center px-4 py-12">
        {error && (
          <div
            role="alert"
            className="mb-6 w-full max-w-lg bg-red-950/50 border border-red-800 text-red-300 rounded-xl px-4 py-3 text-sm"
          >
            {error}
          </div>
        )}
        <OnboardingForm onSubmit={handleSubmit} isLoading={isLoading} />
      </div>
    </div>
  )
}
