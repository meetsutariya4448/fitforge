import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Dumbbell } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Button from '../components/ui/Button'
import { register, login, getWorkoutHistory } from '../services/api'

/**
 * Auth page — Login and Register in a single tabbed view.
 *
 * Register flow: submit form → POST /api/auth/register → save token → redirect /onboarding
 * Login flow:    submit form → POST /api/auth/login    → save token → redirect /onboarding
 */
export default function Auth() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('login')       // 'login' | 'register'
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  // Shared form state — register uses all three, login uses email + password only
  const [form, setForm] = useState({ name: '', email: '', password: '' })

  const handleChange = (e) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
    setError(null)
  }

  const switchTab = (next) => {
    setTab(next)
    setError(null)
    setForm({ name: '', email: '', password: '' })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      let response

      if (tab === 'register') {
        // Register, then the response already includes the token
        response = await register({
          name: form.name,
          email: form.email,
          password: form.password,
        })
      } else {
        // Login
        response = await login({
          email: form.email,
          password: form.password,
        })
      }

      // Save JWT — the Axios interceptor picks this up on every subsequent request
      localStorage.setItem('fitforge_token', response.access_token)

      if (tab === 'register') {
        navigate('/onboarding')
      } else {
        // Returning user: send to plans if they have any, otherwise onboarding
        const { total } = await getWorkoutHistory()
        navigate(total > 0 ? '/plans' : '/onboarding')
      }
    } catch (err) {
      const detail = err.response?.data?.detail
      // detail can be a string or a Pydantic validation array
      if (Array.isArray(detail)) {
        setError(detail.map((d) => d.msg).join(', '))
      } else {
        setError(detail || 'Something went wrong. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center px-4 py-12">
      {/* Logo */}
      <div
        className="flex items-center gap-2 mb-10 cursor-pointer"
        onClick={() => navigate('/')}
      >
        <Dumbbell className="w-6 h-6 text-brand-500" />
        <span className="text-xl font-bold text-white">FitForge</span>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="card w-full max-w-md p-8"
      >
        {/* ── Tabs ── */}
        <div className="flex bg-gray-800 rounded-xl p-1 mb-8">
          {['login', 'register'].map((t) => (
            <button
              key={t}
              onClick={() => switchTab(t)}
              className={`
                flex-1 py-2 rounded-lg text-sm font-semibold transition-all duration-150
                ${tab === t
                  ? 'bg-gray-950 text-white shadow'
                  : 'text-gray-500 hover:text-gray-300'
                }
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
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Name
                </label>
                <input
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
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Email
            </label>
            <input
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
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Password
            </label>
            <input
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

          <Button
            type="submit"
            size="md"
            disabled={isLoading}
            className="w-full mt-2"
          >
            {isLoading
              ? 'Please wait…'
              : tab === 'login' ? 'Log In' : 'Create Account'
            }
          </Button>
        </form>

        {/* ── Switch tab hint ── */}
        <p className="text-center text-sm text-gray-500 mt-6">
          {tab === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button
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
