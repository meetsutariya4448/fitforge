import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Dumbbell, BarChart2, LayoutList, LogIn, LogOut, UserCircle, Menu, X } from 'lucide-react'
import Button from './ui/Button'

/**
 * Shared responsive navbar used on every page.
 *
 * Reads fitforge_token and fitforge_user from localStorage:
 *   - Logged in  → shows Dashboard, My Plans, user first name, Logout
 *   - Logged out → shows Login, Sign Up buttons
 *
 * Collapses to a hamburger menu on mobile (< md breakpoint).
 */
export default function Navbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  const token = localStorage.getItem('fitforge_token')
  const isLoggedIn = !!token
  const user = (() => {
    try { return JSON.parse(localStorage.getItem('fitforge_user') || 'null') }
    catch { return null }
  })()
  const firstName = user?.name?.split(' ')[0] ?? 'Account'

  const handleLogout = () => {
    localStorage.removeItem('fitforge_token')
    localStorage.removeItem('fitforge_user')
    setMenuOpen(false)
    navigate('/')
  }

  const isActive = (path) => location.pathname === path

  const navLinkClass = (path) =>
    `flex items-center gap-1.5 text-sm font-medium transition-colors px-1 py-0.5 ${
      isActive(path)
        ? 'text-brand-400'
        : 'text-gray-400 hover:text-white'
    }`

  return (
    <nav className="border-b border-gray-800 bg-gray-950/90 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        {/* Logo */}
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 flex-shrink-0"
        >
          <Dumbbell className="w-5 h-5 text-brand-500" />
          <span className="text-lg font-bold text-white">FitForge</span>
        </button>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-1">
          {isLoggedIn ? (
            <>
              <button onClick={() => navigate('/dashboard')} className={navLinkClass('/dashboard')}>
                <BarChart2 className="w-4 h-4" /> Dashboard
              </button>
              <button onClick={() => navigate('/plans')} className={navLinkClass('/plans')}>
                <LayoutList className="w-4 h-4" /> My Plans
              </button>
              <span className="mx-2 text-gray-700">|</span>
              <span className="flex items-center gap-1.5 text-sm text-gray-400 mr-2">
                <UserCircle className="w-4 h-4" /> {firstName}
              </span>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="w-4 h-4 mr-1.5" /> Logout
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" onClick={() => navigate('/auth')}>
                <LogIn className="w-4 h-4 mr-1.5" /> Login
              </Button>
              <Button size="sm" onClick={() => navigate('/auth')}>
                Sign Up
              </Button>
            </>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden text-gray-400 hover:text-white transition-colors"
          onClick={() => setMenuOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {menuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="md:hidden border-t border-gray-800 px-6 py-4 space-y-3 bg-gray-950">
          {isLoggedIn ? (
            <>
              <button
                onClick={() => { navigate('/dashboard'); setMenuOpen(false) }}
                className={`${navLinkClass('/dashboard')} w-full text-left`}
              >
                <BarChart2 className="w-4 h-4" /> Dashboard
              </button>
              <button
                onClick={() => { navigate('/plans'); setMenuOpen(false) }}
                className={`${navLinkClass('/plans')} w-full text-left`}
              >
                <LayoutList className="w-4 h-4" /> My Plans
              </button>
              <div className="pt-2 border-t border-gray-800 flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-sm text-gray-400">
                  <UserCircle className="w-4 h-4" /> {firstName}
                </span>
                <Button variant="ghost" size="sm" onClick={handleLogout}>
                  <LogOut className="w-4 h-4 mr-1.5" /> Logout
                </Button>
              </div>
            </>
          ) : (
            <div className="flex gap-3">
              <Button variant="ghost" size="sm" onClick={() => { navigate('/auth'); setMenuOpen(false) }}>
                <LogIn className="w-4 h-4 mr-1.5" /> Login
              </Button>
              <Button size="sm" onClick={() => { navigate('/auth'); setMenuOpen(false) }}>
                Sign Up
              </Button>
            </div>
          )}
        </div>
      )}
    </nav>
  )
}
