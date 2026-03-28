import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Onboarding from './pages/Onboarding'
import WorkoutPlanPage from './pages/WorkoutPlanPage'

/**
 * Root component — defines all client-side routes.
 *
 * /             → Landing page
 * /onboarding   → Multi-step onboarding form
 * /plan         → Generated workout plan display
 */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/plan" element={<WorkoutPlanPage />} />
    </Routes>
  )
}
