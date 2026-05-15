import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Dumbbell, TrendingUp, LayoutList, Home, Zap,
  Calendar, Flame, BarChart2, Activity, LogOut, LogIn,
} from 'lucide-react'
import { motion } from 'framer-motion'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import Button from '../components/ui/Button'
import { getWorkoutSessions } from '../services/api'

export default function Dashboard() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [isLoggedIn, setIsLoggedIn] = useState(() => !!localStorage.getItem('fitforge_token'))

  const handleLogout = () => {
    localStorage.removeItem('fitforge_token')
    setIsLoggedIn(false)
    navigate('/auth')
  }

  useEffect(() => {
    getWorkoutSessions()
      .then((res) => setSessions(Array.isArray(res) ? res : []))
      .catch(() => setSessions([]))
      .finally(() => setLoading(false))
  }, [])

  // ── Derived stats ──────────────────────────────────────────────────────────

  const totalSessions = sessions.length

  const totalVolume = sessions.reduce((sum, s) =>
    sum + s.exercise_logs.reduce((logSum, l) =>
      logSum + l.sets_completed * l.reps_completed * (l.weight_kg || 0), 0), 0)

  const exerciseCounts = {}
  sessions.forEach((s) =>
    s.exercise_logs.forEach((l) => {
      exerciseCounts[l.exercise_name] = (exerciseCounts[l.exercise_name] || 0) + 1
    })
  )
  const topExercises = Object.entries(exerciseCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name, count]) => ({ name, count }))

  // Volume over last 8 sessions (chronological)
  const volumeData = [...sessions]
    .reverse()
    .slice(-8)
    .map((s) => ({
      label: s.day_name.slice(0, 8),
      volume: Math.round(
        s.exercise_logs.reduce(
          (sum, l) => sum + l.sets_completed * l.reps_completed * (l.weight_kg || 0), 0
        )
      ),
    }))

  // Weekly consistency — sessions per week for last 6 weeks
  const weeklyMap = {}
  sessions.forEach((s) => {
    const d = new Date(s.session_date)
    const monday = new Date(d)
    monday.setDate(d.getDate() - ((d.getDay() + 6) % 7))
    const key = monday.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    weeklyMap[key] = (weeklyMap[key] || 0) + 1
  })
  const weeklyData = Object.entries(weeklyMap)
    .slice(-6)
    .map(([week, count]) => ({ week, count }))

  const stats = [
    { label: 'Total Sessions', value: totalSessions, icon: <Calendar className="w-5 h-5" />, color: 'text-brand-400' },
    { label: 'Total Volume (kg)', value: Math.round(totalVolume).toLocaleString(), icon: <Flame className="w-5 h-5" />, color: 'text-orange-400' },
    { label: 'Exercises Tracked', value: Object.keys(exerciseCounts).length, icon: <BarChart2 className="w-5 h-5" />, color: 'text-purple-400' },
    { label: 'This Week', value: weeklyData.at(-1)?.count ?? 0, icon: <Activity className="w-5 h-5" />, color: 'text-green-400' },
  ]

  return (
    <div className="min-h-screen bg-gray-950 pb-24">
      {/* ── Navbar ── */}
      <nav className="border-b border-gray-800 px-6 py-4 sticky top-0 bg-gray-950/90 backdrop-blur-sm z-10">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Dumbbell className="w-5 h-5 text-brand-500" />
            <span className="text-lg font-bold text-white">FitForge</span>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate('/plans')}>
              <LayoutList className="w-4 h-4 mr-1.5" />
              My Plans
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
              <Home className="w-4 h-4 mr-1.5" />
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

      <main className="max-w-5xl mx-auto px-4 pt-10 space-y-10">
        {/* ── Page title ── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="flex items-center gap-2 text-brand-400 text-sm font-medium mb-2">
            <TrendingUp className="w-4 h-4" />
            Progress Dashboard
          </div>
          <h1 className="text-3xl font-extrabold text-white">Your Training Overview</h1>
        </motion.div>

        {/* ── Stat cards ── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="grid grid-cols-2 sm:grid-cols-4 gap-4"
        >
          {stats.map((stat) => (
            <div key={stat.label} className="card p-5">
              <div className={`mb-3 ${stat.color}`}>{stat.icon}</div>
              <div className="text-2xl font-extrabold text-white">{loading ? '—' : stat.value}</div>
              <div className="text-xs text-gray-500 mt-1">{stat.label}</div>
            </div>
          ))}
        </motion.div>

        {loading ? (
          <div className="text-center text-gray-500 py-20">Loading sessions…</div>
        ) : sessions.length === 0 ? (
          <div className="card p-12 text-center">
            <Dumbbell className="w-10 h-10 text-gray-700 mx-auto mb-4" />
            <p className="text-gray-400 mb-6">No workout sessions logged yet.</p>
            <Button onClick={() => navigate('/onboarding')}>
              <Zap className="w-4 h-4 mr-2" />
              Generate My First Plan
            </Button>
          </div>
        ) : (
          <>
            {/* ── Volume over time ── */}
            {volumeData.length > 0 && (
              <motion.section
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.2 }}
                className="card p-6"
              >
                <h2 className="font-semibold text-white mb-6">Volume Over Time (kg)</h2>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={volumeData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis dataKey="label" tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                      labelStyle={{ color: '#9ca3af' }}
                      itemStyle={{ color: '#34d399' }}
                    />
                    <Line type="monotone" dataKey="volume" stroke="#10b981" strokeWidth={2} dot={{ fill: '#10b981', r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </motion.section>
            )}

            {/* ── Weekly consistency ── */}
            {weeklyData.length > 0 && (
              <motion.section
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.3 }}
                className="card p-6"
              >
                <h2 className="font-semibold text-white mb-6">Weekly Consistency</h2>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={weeklyData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis dataKey="week" tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                      labelStyle={{ color: '#9ca3af' }}
                      itemStyle={{ color: '#818cf8' }}
                    />
                    <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </motion.section>
            )}

            {/* ── Top exercises ── */}
            {topExercises.length > 0 && (
              <motion.section
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.4 }}
                className="card p-6"
              >
                <h2 className="font-semibold text-white mb-6">Top Exercises</h2>
                <ResponsiveContainer width="100%" height={topExercises.length * 44 + 16}>
                  <BarChart
                    data={topExercises}
                    layout="vertical"
                    margin={{ top: 4, right: 8, bottom: 4, left: 100 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <YAxis type="category" dataKey="name" tick={{ fill: '#d1d5db', fontSize: 12 }} width={96} />
                    <Tooltip
                      contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                      labelStyle={{ color: '#9ca3af' }}
                      itemStyle={{ color: '#fb923c' }}
                    />
                    <Bar dataKey="count" fill="#f97316" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </motion.section>
            )}

            {/* ── Recent sessions ── */}
            <motion.section
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.5 }}
            >
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
                Recent Sessions
              </h2>
              <div className="space-y-3">
                {sessions.slice(0, 5).map((s) => (
                  <div key={s.id} className="card p-4 flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-white text-sm">{s.day_name}</div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {new Date(s.session_date).toLocaleDateString('en-US', {
                          month: 'short', day: 'numeric', year: 'numeric',
                        })}
                        {' · '}
                        {s.exercise_logs.length} exercises
                      </div>
                    </div>
                    <div className="text-xs text-gray-400">
                      {Math.round(
                        s.exercise_logs.reduce(
                          (sum, l) => sum + l.sets_completed * l.reps_completed * (l.weight_kg || 0), 0
                        )
                      ).toLocaleString()} kg
                    </div>
                  </div>
                ))}
              </div>
            </motion.section>
          </>
        )}

        {/* ── Generate from progress CTA ── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.6 }}
          className="card p-6 flex flex-col sm:flex-row items-center justify-between gap-4"
        >
          <div>
            <p className="font-semibold text-white">Ready for a new plan?</p>
            <p className="text-sm text-gray-400 mt-1">
              Generate a personalised plan that adapts to your logged progress.
            </p>
          </div>
          <Button onClick={() => navigate('/onboarding')} className="flex-shrink-0">
            <Zap className="w-4 h-4 mr-2" />
            Generate New Plan
          </Button>
        </motion.div>
      </main>
    </div>
  )
}
