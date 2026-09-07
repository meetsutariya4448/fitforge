/**
 * Animated progress bar used in the onboarding flow.
 */
export interface ProgressBarProps {
  /** Percentage complete, 0–100. Values outside the range are clamped. */
  value: number
  /** Extra Tailwind classes for the wrapper. */
  className?: string
}

export default function ProgressBar({ value, className = '' }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value))

  return (
    <div className={`h-1.5 bg-gray-800 rounded-full overflow-hidden ${className}`}>
      <div
        className="h-full bg-brand-500 rounded-full transition-all duration-500 ease-out"
        style={{ width: `${clamped}%` }}
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
      />
    </div>
  )
}
