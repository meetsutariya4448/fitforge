import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Auth from './pages/Auth'
import Onboarding from './pages/Onboarding'
import WorkoutPlanPage from './pages/WorkoutPlanPage'
import PlansHistory from './pages/PlansHistory'
import Dashboard from './pages/Dashboard'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/auth" element={<Auth />} />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/plan" element={<WorkoutPlanPage />} />
      <Route path="/plans" element={<PlansHistory />} />
      <Route path="/dashboard" element={<Dashboard />} />
    </Routes>
  )
}
