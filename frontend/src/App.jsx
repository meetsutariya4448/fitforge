import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Auth from './pages/Auth'
import Onboarding from './pages/Onboarding'
import WorkoutPlanPage from './pages/WorkoutPlanPage'
import PlansHistory from './pages/PlansHistory'

/**
 * Root component — defines all client-side routes.
 *
 * /             → Landing page
 * /auth         → Login / Register
 * /onboarding   → Multi-step onboarding form (requires auth)
 * /plan         → Generated workout plan display
 * /plans        → Saved plan history (requires auth)
 */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/auth" element={<Auth />} />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/plan" element={<WorkoutPlanPage />} />
      <Route path="/plans" element={<PlansHistory />} />
    </Routes>
  )
}
