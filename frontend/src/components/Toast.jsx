import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, XCircle, X } from 'lucide-react'

/**
 * Toast notification component.
 *
 * @param {string}   message  - Text to display
 * @param {'success'|'error'} type - Controls colour scheme
 * @param {Function} onClose  - Called after auto-dismiss or manual close
 */
export default function Toast({ message, type = 'success', onClose }) {
  // Auto-dismiss after 3 seconds
  useEffect(() => {
    const timer = setTimeout(onClose, 3000)
    return () => clearTimeout(timer)
  }, [onClose])

  const isSuccess = type === 'success'

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 16, scale: 0.95 }}
        transition={{ duration: 0.2 }}
        className={`
          fixed bottom-6 right-6 z-50
          flex items-center gap-3
          px-4 py-3 rounded-xl shadow-xl
          text-sm font-medium
          ${isSuccess
            ? 'bg-brand-500/10 border border-brand-500/30 text-brand-300'
            : 'bg-red-950/60 border border-red-700/50 text-red-300'
          }
        `}
        role="status"
        aria-live="polite"
      >
        {isSuccess
          ? <CheckCircle className="w-4 h-4 flex-shrink-0 text-brand-400" />
          : <XCircle className="w-4 h-4 flex-shrink-0 text-red-400" />
        }
        <span>{message}</span>
        <button
          onClick={onClose}
          className="ml-1 text-current opacity-50 hover:opacity-100 transition-opacity"
          aria-label="Dismiss"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </motion.div>
    </AnimatePresence>
  )
}
