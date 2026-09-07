import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Dumbbell } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

import Button from '../components/ui/Button'
import { useAuth } from '../contexts/AuthContext'
import { getWorkoutHistory, toApiError } from '../services/api'

/**
 * Auth page — Login and Register in a single tabbed view.
 *
 * Register flow: submit form → POST /api/auth/register → session stored → /onboarding
 * Login flow:    submit form → POST /api/auth/login    → session stored → /plans or /onboarding
 */

type Tab = 'login' | 'register'

interface FormState {
  name: string
  email: string
  password: string
}

const EMPTY_FORM: FormState = { name: '', email: '', password: '' }

/** Where to land after signing in, honouring an interrupted navigation. */
interface FromState {
  from?: { pathname?: string }
}

export default function Auth() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login, register } = useAuth()

  useEffect(() => {
    document.title = 'FitForge — Sign In'
  }, [])

  const [tab, setTab] = useState<Tab>('login')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)

  const handleChange = (e: ChangeEvent<HTMLInputElement>): void => {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setError(null)
  }

  const switchTab = (next: Tab): void => {
    setTab(next)
    setError(null)
    setForm(EMPTY_FORM)
  }

  const handleSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      if (tab === 'register') {
        await register({ name: form.name, email: form.email, password: form.password })
        navigate('/onboarding')
        return
      }

      await login({ email: form.email, password: form.password })

      // An interrupted navigation wins; otherwise returning users go to their
      // plans and first-timers to onboarding.
      const redirectTo = (location.state as FromState | null)?.from?.pathname
      if (redirectTo && redirectTo !== '/auth') {
        navigate(redirectTo, { replace: true })
        return
      }

      const { total } = await getWorkoutHistory()
      navigate(total > 0 ? '/plans' : '/onboarding')
    } catch (err) {
      // toApiError normalises axios, network and schema failures into one shape
      // with a message worth showing. The old code read `data.detail`, which the
      // API's {"error": {code, message}} envelope never contained, so every
      // server-supplied reason resolved to undefined and users saw only the
      // generic fallback.
      setError(toApiError(err).message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center px-4 py-12">
      {/* Logo */}
      <button
        type="button"
        className="flex items-center gap-2 mb-10 cursor-pointer"
        onClick={() => navigate('/')}
      >
        <Dumbbell className="w-6 h-6 text-brand-500" />
        <span className="text-xl font-bold text-white">FitForge</span>
      </button>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="card w-full max-w-md p-8"
      >
        {/* ── Tabs ── */}
        <div className="flex bg-gray-800 rounded-xl p-1 mb-8">
          {(['login', 'register'] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => switchTab(t)}
              className={`
                flex-1 py-2 rounded-lg text-sm font-semibold transition-all duration-150
                ${tab === t ? 'bg-gray-950 text-white shadow' : 'text-gray-500 hover:text-gray-300'}
              `}
            >
              {t === 'login' ? 'Log In' : 'Register'}
            </button>
          ))}
        </div>

        {/* ── Error banner ── */}
        <AnimatePresence>
          {error && (
            <motion.div
              key="auth-error"
              role="alert"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-5 bg-red-950/50 border border-red-800 text-red-300 rounded-xl px-4 py-3 text-sm overflow-hidden"
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Form ── */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <AnimatePresence initial={false}>
            {tab === 'register' && (
              <motion.div
                key="name-field"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <label htmlFor="name" className="block text-sm font-medium text-gray-300 mb-1.5">
                  Name
                </label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  value={form.name}
                  onChange={handleChange}
                  placeholder="Your name"
                  required={tab === 'register'}
                  className="input"
                  autoComplete="name"
                />
              </motion.div>
            )}
          </AnimatePresence>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1.5">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="you@example.com"
              required
              className="input"
              autoComplete="email"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-1.5">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              placeholder={tab === 'register' ? 'Min. 8 characters' : '••••••••'}
              required
              minLength={tab === 'register' ? 8 : undefined}
              className="input"
              autoComplete={tab === 'register' ? 'new-password' : 'current-password'}
            />
          </div>

          <Button type="submit" size="md" disabled={isLoading} className="w-full mt-2">
            {isLoading ? 'Please wait…' : tab === 'login' ? 'Log In' : 'Create Account'}
          </Button>
        </form>

        {/* ── Switch tab hint ── */}
        <p className="text-center text-sm text-gray-500 mt-6">
          {tab === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button
            type="button"
            onClick={() => switchTab(tab === 'login' ? 'register' : 'login')}
            className="text-brand-400 hover:text-brand-300 font-medium transition-colors"
          >
            {tab === 'login' ? 'Register' : 'Log In'}
          </button>
        </p>
      </motion.div>
    </div>
  )
}
