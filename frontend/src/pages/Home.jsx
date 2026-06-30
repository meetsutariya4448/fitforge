import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Brain, TrendingUp, Users, ArrowRight, Zap, Trophy } from 'lucide-react'
import { motion } from 'framer-motion'
import Button from '../components/ui/Button'
import Navbar from '../components/Navbar'
import { loginDemo } from '../services/api'

export default function Home() {
  const navigate = useNavigate()
  const [demoLoading, setDemoLoading] = useState(false)
  const [demoError, setDemoError] = useState(null)

  useEffect(() => { document.title = 'FitForge — AI Fitness Platform' }, [])

  const handleDemo = async () => {
    setDemoLoading(true)
    setDemoError(null)
    try {
      const res = await loginDemo()
      localStorage.setItem('fitforge_token', res.access_token)
      if (res.user) localStorage.setItem('fitforge_user', JSON.stringify(res.user))
      navigate('/dashboard')
    } catch {
      setDemoError('Demo login failed — try again')
    } finally {
      setDemoLoading(false)
    }
  }

  const features = [
    {
      icon: <Brain className="w-6 h-6" />,
      title: 'AI-Personalised Plans',
      description: 'Groq AI analyses your goals, fitness level, and equipment to craft a plan made specifically for you.',
    },
    {
      icon: <TrendingUp className="w-6 h-6" />,
      title: 'Progress Tracking',
      description: 'Log workouts, track volume over time, and visualise your improvements with interactive charts.',
    },
    {
      icon: <Trophy className="w-6 h-6" />,
      title: 'Personal Records',
      description: 'Automatically track your all-time best weight and reps for every exercise you log.',
    },
    {
      icon: <Users className="w-6 h-6" />,
      title: 'Built for Builders',
      description: 'Open-source portfolio project — full-stack React + FastAPI + PostgreSQL + Groq AI.',
    },
  ]

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      <Navbar />

      {/* ── Hero ── */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 sm:px-6 py-16 sm:py-24 text-center">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-3xl mx-auto w-full"
        >
          <div className="inline-flex items-center gap-2 bg-brand-500/10 text-brand-400 text-sm font-medium px-4 py-1.5 rounded-full mb-8 border border-brand-500/20">
            <Zap className="w-4 h-4" />
            Powered by Groq AI
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white leading-tight mb-6">
            Your Personal{' '}
            <span className="text-brand-500">AI Trainer</span>{' '}
            Is Ready
          </h1>

          <p className="text-lg sm:text-xl text-gray-400 mb-10 max-w-2xl mx-auto leading-relaxed">
            Answer 5 quick questions about your goals, fitness level, and available equipment.
            Get a personalised weekly workout plan in seconds — no gym required.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button size="lg" onClick={() => navigate('/auth')} className="group w-full sm:w-auto">
              Build My Plan
              <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
            </Button>
            <Button
              size="lg"
              variant="ghost"
              onClick={handleDemo}
              disabled={demoLoading}
              className="w-full sm:w-auto"
            >
              {demoLoading ? 'Logging in…' : 'Try Demo'}
            </Button>
          </div>

          {demoError && (
            <p className="mt-4 text-sm text-red-400">{demoError}</p>
          )}

          <p className="mt-3 text-xs text-gray-600">
            Demo: demo@fitforge.app / Demo1234!
          </p>
        </motion.div>

        {/* ── Feature Cards ── */}
        <motion.div
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mt-20 sm:mt-24 max-w-6xl w-full"
        >
          {features.map((feature) => (
            <div key={feature.title} className="card p-5 sm:p-6 text-left hover:border-gray-700 transition-colors">
              <div className="w-11 h-11 bg-brand-500/10 text-brand-500 rounded-xl flex items-center justify-center mb-4">
                {feature.icon}
              </div>
              <h3 className="font-semibold text-white mb-2 text-sm sm:text-base">{feature.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </motion.div>
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-gray-800 py-6 text-center text-gray-600 text-sm px-4">
        Built with React + FastAPI + PostgreSQL + Groq AI · Portfolio project by{' '}
        <span className="text-gray-400">Meet Sutariya</span>
      </footer>
    </div>
  )
}
