import { Routes, Route } from 'react-router-dom'

import RequireAuth from './components/RequireAuth'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'
import Home from './pages/Home'
import Onboarding from './pages/Onboarding'
import PlansHistory from './pages/PlansHistory'
import WorkoutPlanPage from './pages/WorkoutPlanPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/auth" element={<Auth />} />
      {/* Everything below needs a session. RequireAuth waits for the stored
          session to load before deciding, so a hard refresh on one of these
          pages no longer bounces a signed-in user to /auth. */}
      <Route
        path="/onboarding"
        element={
          <RequireAuth>
            <Onboarding />
          </RequireAuth>
        }
      />
      <Route
        path="/plan"
        element={
          <RequireAuth>
            <WorkoutPlanPage />
          </RequireAuth>
        }
      />
      <Route
        path="/plans"
        element={
          <RequireAuth>
            <PlansHistory />
          </RequireAuth>
        }
      />
      <Route
        path="/dashboard"
        element={
          <RequireAuth>
            <Dashboard />
          </RequireAuth>
        }
      />
    </Routes>
  )
}
