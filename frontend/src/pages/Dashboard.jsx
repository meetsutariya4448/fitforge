import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Dumbbell, TrendingUp, Zap,
  Calendar, Flame, Trophy, Activity,
  ChevronDown, ChevronUp,
} from 'lucide-react'
import { motion } from 'framer-motion'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import Button from '../components/ui/Button'
import Navbar from '../components/Navbar'
import { getWorkoutSessions, getPRs, getExerciseTrend } from '../services/api'

export default function Dashboard() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState([])
  const [prs, setPRs] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedSession, setExpandedSession] = useState(null)

  // Strength trend state
  const [trendExercise, setTrendExercise] = useState('')
  const [trendData, setTrendData] = useState(null)
  const [trendLoading, setTrendLoading] = useState(false)

  useEffect(() => {
    document.title = 'FitForge — Dashboard'
    if (!localStorage.getItem('fitforge_token')) {
      navigate('/auth', { replace: true })
      return
    }
    Promise.all([getWorkoutSessions(), getPRs()])
      .then(([sess, prList]) => {
        setSessions(Array.isArray(sess) ? sess : [])
        setPRs(Array.isArray(prList) ? prList : [])
      })
      .catch(() => { setSessions([]); setPRs([]) })
      .finally(() => setLoading(false))
  }, [navigate])

  // Fetch trend when exercise selection changes
  useEffect(() => {
    if (!trendExercise) { setTrendData(null); return }
    setTrendLoading(true)
    getExerciseTrend(trendExercise)
      .then((res) => setTrendData(res))
      .catch(() => setTrendData(null))
      .finally(() => setTrendLoading(false))
  }, [trendExercise])

  // ── Derived stats ──────────────────────────────────────────────────────────

  const totalVolume = sessions.reduce((sum, s) =>
    sum + s.exercise_logs.reduce((ls, l) =>
      ls + l.sets_completed * l.reps_completed * (l.weight_kg || 0), 0), 0)

  const exerciseCounts = {}
  sessions.forEach((s) =>
    s.exercise_logs.forEach((l) => {
      exerciseCounts[l.exercise_name] = (exerciseCounts[l.exercise_name] || 0) + 1
    })
  )
  const uniqueExercises = Object.keys(exerciseCounts).sort()

  const topExercises = Object.entries(exerciseCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name, count]) => ({ name, count }))

  const topExerciseName = topExercises[0]?.name ?? '—'

  const now = new Date()
  const thisMonday = new Date(now)
  thisMonday.setDate(now.getDate() - ((now.getDay() + 6) % 7))
  thisMonday.setHours(0, 0, 0, 0)
  const sessionsThisWeek = sessions.filter(
    (s) => new Date(s.session_date) >= thisMonday
  ).length

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

  const weeklyMap = {}
  sessions.forEach((s) => {
    const d = new Date(s.session_date)
    const mon = new Date(d)
    mon.setDate(d.getDate() - ((d.getDay() + 6) % 7))
    const key = mon.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    weeklyMap[key] = (weeklyMap[key] || 0) + 1
  })
  const weeklyData = Object.entries(weeklyMap).slice(-8).map(([week, count]) => ({ week, count }))

  const stats = [
    { label: 'Total Sessions', value: sessions.length, icon: <Calendar className="w-5 h-5" />, color: 'text-brand-400' },
    { label: 'Total Volume (kg)', value: Math.round(totalVolume).toLocaleString(), icon: <Flame className="w-5 h-5" />, color: 'text-orange-400' },
    { label: 'Sessions This Week', value: sessionsThisWeek, icon: <Activity className="w-5 h-5" />, color: 'text-green-400' },
    { label: 'Most Trained', value: topExerciseName, icon: <Trophy className="w-5 h-5" />, color: 'text-yellow-400', small: true },
  ]

  const trendChartData = (trendData?.data || []).map((p) => ({
    date: new Date(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    weight: p.max_weight_kg ?? 0,
    volume: Math.round(p.total_volume),
  }))

  return (
    <div className="min-h-screen bg-gray-950 pb-24">
      <Navbar />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 pt-10 space-y-10">
        {/* ── Page title ── */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <div className="flex items-center gap-2 text-brand-400 text-sm font-medium mb-2">
            <TrendingUp className="w-4 h-4" /> Progress Dashboard
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white">Your Training Overview</h1>
        </motion.div>

        {/* ── Stat cards ── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}
          className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4"
        >
          {stats.map((stat) => (
            <div key={stat.label} className="card p-4 sm:p-5">
              <div className={`mb-3 ${stat.color}`}>{stat.icon}</div>
              <div className={`font-extrabold text-white ${stat.small ? 'text-sm truncate' : 'text-xl sm:text-2xl'}`}>
                {loading ? '—' : stat.value}
              </div>
              <div className="text-xs text-gray-500 mt-1">{stat.label}</div>
            </div>
          ))}
        </motion.div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-10 h-10 border-4 border-gray-700 border-t-brand-500 rounded-full animate-spin" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="card p-10 sm:p-12 text-center">
            <Dumbbell className="w-10 h-10 text-gray-700 mx-auto mb-4" />
            <p className="text-gray-400 mb-6">No workout sessions logged yet.</p>
            <Button onClick={() => navigate('/onboarding')}>
              <Zap className="w-4 h-4 mr-2" /> Generate My First Plan
            </Button>
          </div>
        ) : (
          <>
            {/* ── Volume over time ── */}
            <motion.section
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.2 }}
              className="card p-4 sm:p-6"
            >
              <h2 className="font-semibold text-white mb-6">Volume Over Time (kg)</h2>
              {volumeData.length < 2 ? (
                <p className="text-gray-500 text-sm text-center py-8">Log at least 2 workouts to see volume trends.</p>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={volumeData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis dataKey="label" tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }} labelStyle={{ color: '#9ca3af' }} itemStyle={{ color: '#34d399' }} />
                    <Line type="monotone" dataKey="volume" stroke="#10b981" strokeWidth={2} dot={{ fill: '#10b981', r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </motion.section>

            {/* ── Weekly consistency ── */}
            {weeklyData.length > 0 && (
              <motion.section
                initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.3 }}
                className="card p-4 sm:p-6"
              >
                <h2 className="font-semibold text-white mb-6">Weekly Consistency</h2>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={weeklyData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis dataKey="week" tick={{ fill: '#6b7280', fontSize: 10 }} />
                    <YAxis allowDecimals={false} tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }} labelStyle={{ color: '#9ca3af' }} itemStyle={{ color: '#818cf8' }} />
                    <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </motion.section>
            )}

            {/* ── Top exercises ── */}
            {topExercises.length > 0 && (
              <motion.section
                initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.4 }}
                className="card p-4 sm:p-6"
              >
                <h2 className="font-semibold text-white mb-6">Top 5 Exercises</h2>
                <ResponsiveContainer width="100%" height={topExercises.length * 44 + 16}>
                  <BarChart data={topExercises} layout="vertical" margin={{ top: 4, right: 8, bottom: 4, left: 100 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <YAxis type="category" dataKey="name" tick={{ fill: '#d1d5db', fontSize: 12 }} width={96} />
                    <Tooltip contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }} labelStyle={{ color: '#9ca3af' }} itemStyle={{ color: '#fb923c' }} />
                    <Bar dataKey="count" fill="#f97316" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </motion.section>
            )}

            {/* ── Personal Records ── */}
            <motion.section
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.45 }}
            >
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
                Personal Records
              </h2>
              {prs.length === 0 ? (
                <div className="card p-8 text-center text-gray-500 text-sm">
                  Log workouts to start tracking your PRs 🏆
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {prs.map((pr) => (
                    <div key={pr.id} className="card p-4 flex items-start gap-3">
                      <div className="w-9 h-9 rounded-xl bg-yellow-500/10 flex items-center justify-center flex-shrink-0">
                        <Trophy className="w-4 h-4 text-yellow-400" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-white text-sm truncate">{pr.exercise_name}</p>
                        <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
                          {pr.max_weight_kg != null && (
                            <span className="text-xs text-brand-400 font-medium">{pr.max_weight_kg} kg</span>
                          )}
                          {pr.max_reps != null && (
                            <span className="text-xs text-gray-400">{pr.max_reps} reps</span>
                          )}
                        </div>
                        <p className="text-xs text-gray-600 mt-1">
                          {new Date(pr.achieved_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </motion.section>

            {/* ── Strength Trends ── */}
            <motion.section
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.5 }}
              className="card p-4 sm:p-6"
            >
              <h2 className="font-semibold text-white mb-4">Strength Trends</h2>
              <div className="mb-5">
                <label className="text-xs text-gray-500 mb-1 block">Select exercise</label>
                <select
                  value={trendExercise}
                  onChange={(e) => setTrendExercise(e.target.value)}
                  className="select text-sm py-2 w-full sm:w-72"
                >
                  <option value="">— Choose an exercise —</option>
                  {uniqueExercises.map((ex) => (
                    <option key={ex} value={ex}>{ex}</option>
                  ))}
                </select>
              </div>

              {!trendExercise ? (
                <p className="text-gray-600 text-sm text-center py-6">Select an exercise above to see your strength trend.</p>
              ) : trendLoading ? (
                <div className="flex justify-center py-8">
                  <div className="w-8 h-8 border-4 border-gray-700 border-t-brand-500 rounded-full animate-spin" />
                </div>
              ) : !trendData || trendChartData.length < 2 ? (
                <p className="text-gray-500 text-sm text-center py-6">
                  Log at least 2 sessions with <span className="text-white">{trendExercise}</span> to see your trend.
                </p>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={trendChartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                    <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} unit=" kg" />
                    <Tooltip
                      contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                      labelStyle={{ color: '#9ca3af' }}
                      itemStyle={{ color: '#a78bfa' }}
                      formatter={(v) => [`${v} kg`, 'Weight']}
                    />
                    <Line type="monotone" dataKey="weight" stroke="#8b5cf6" strokeWidth={2} dot={{ fill: '#8b5cf6', r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </motion.section>

            {/* ── Recent sessions (expandable) ── */}
            <motion.section
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.55 }}
            >
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
                Recent Sessions
              </h2>
              <div className="space-y-3">
                {sessions.slice(0, 5).map((s) => (
                  <div key={s.id} className="card overflow-hidden">
                    <button
                      onClick={() => setExpandedSession(expandedSession === s.id ? null : s.id)}
                      className="w-full p-4 flex items-center justify-between hover:bg-gray-800/50 transition-colors"
                    >
                      <div className="text-left min-w-0">
                        <div className="font-semibold text-white text-sm">{s.day_name}</div>
                        <div className="text-xs text-gray-500 mt-0.5">
                          {new Date(s.session_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                          {' · '}{s.exercise_logs.length} exercises
                        </div>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0 ml-3">
                        <span className="text-xs text-gray-400">
                          {Math.round(s.exercise_logs.reduce((sum, l) => sum + l.sets_completed * l.reps_completed * (l.weight_kg || 0), 0)).toLocaleString()} kg
                        </span>
                        {expandedSession === s.id
                          ? <ChevronUp className="w-4 h-4 text-gray-500" />
                          : <ChevronDown className="w-4 h-4 text-gray-500" />
                        }
                      </div>
                    </button>
                    {expandedSession === s.id && (
                      <div className="px-4 pb-4 pt-3 border-t border-gray-800 space-y-1.5">
                        {s.exercise_logs.map((l, i) => (
                          <div key={i} className="flex items-center justify-between text-xs py-1">
                            <span className="text-gray-300">{l.exercise_name}</span>
                            <span className="text-gray-500">
                              {l.sets_completed}×{l.reps_completed}{l.weight_kg ? ` @ ${l.weight_kg}kg` : ''}
                            </span>
                          </div>
                        ))}
                        {s.notes && <p className="text-xs text-gray-600 italic pt-2 border-t border-gray-800 mt-1">{s.notes}</p>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </motion.section>
          </>
        )}

        {/* ── CTA ── */}
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.6 }}
          className="card p-5 sm:p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        >
          <div>
            <p className="font-semibold text-white">Ready for a new plan?</p>
            <p className="text-sm text-gray-400 mt-1">Generate a personalised plan that adapts to your logged progress.</p>
          </div>
          <Button onClick={() => navigate('/onboarding')} className="flex-shrink-0 w-full sm:w-auto">
            <Zap className="w-4 h-4 mr-2" /> Generate New Plan
          </Button>
        </motion.div>
      </main>
    </div>
  )
}
