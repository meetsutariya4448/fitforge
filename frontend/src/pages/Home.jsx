import { useNavigate } from 'react-router-dom'
import { Dumbbell, Brain, TrendingUp, Users, ArrowRight, Zap, LayoutList } from 'lucide-react'
import { motion } from 'framer-motion'
import Button from '../components/ui/Button'

/**
 * Landing page — introduces FitForge and drives users to start onboarding.
 */
export default function Home() {
  const navigate = useNavigate()

  const features = [
    {
      icon: <Brain className="w-6 h-6" />,
      title: 'AI-Personalised Plans',
      description: 'Claude AI analyses your goals, fitness level, and equipment to craft a plan made specifically for you.',
    },
    {
      icon: <TrendingUp className="w-6 h-6" />,
      title: 'Progress Tracking',
      description: 'Log workouts, track PRs, and visualise your improvements over time with interactive charts.',
    },
    {
      icon: <Users className="w-6 h-6" />,
      title: 'Social Layer',
      description: 'Share achievements, follow training partners, and stay accountable with a fitness community.',
    },
  ]

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* ── Navbar ── */}
      <nav className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Dumbbell className="w-6 h-6 text-brand-500" />
            <span className="text-xl font-bold text-white">FitForge</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => navigate('/plans')}>
              <LayoutList className="w-4 h-4 mr-1.5" />
              My Plans
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate('/onboarding')}>
              Get Started
            </Button>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 py-24 text-center">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="max-w-3xl mx-auto"
        >
          <div className="inline-flex items-center gap-2 bg-brand-500/10 text-brand-400 text-sm font-medium px-4 py-1.5 rounded-full mb-8 border border-brand-500/20">
            <Zap className="w-4 h-4" />
            Powered by Claude AI
          </div>

          <h1 className="text-5xl sm:text-6xl font-extrabold text-white leading-tight mb-6">
            Your Personal{' '}
            <span className="text-brand-500">AI Trainer</span>{' '}
            Is Ready
          </h1>

          <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto leading-relaxed">
            Answer 5 quick questions about your goals, fitness level, and available equipment.
            Get a personalised weekly workout plan in seconds — no gym required.
          </p>

          <Button
            size="lg"
            onClick={() => navigate('/onboarding')}
            className="group"
          >
            Build My Plan
            <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
          </Button>
        </motion.div>

        {/* ── Feature Cards ── */}
        <motion.div
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-24 max-w-5xl w-full"
        >
          {features.map((feature) => (
            <div key={feature.title} className="card p-6 text-left hover:border-gray-700 transition-colors">
              <div className="w-12 h-12 bg-brand-500/10 text-brand-500 rounded-xl flex items-center justify-center mb-4">
                {feature.icon}
              </div>
              <h3 className="font-semibold text-white mb-2">{feature.title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </motion.div>
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-gray-800 py-6 text-center text-gray-600 text-sm">
        Built with React + FastAPI + Claude API · Portfolio project by{' '}
        <span className="text-gray-400">Meet Sutariya</span>
      </footer>
    </div>
  )
}
