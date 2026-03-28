/**
 * Reusable Button component with variant and size options.
 *
 * Variants: primary (default), ghost
 * Sizes:    sm, md, lg
 */
export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  className = '',
  onClick,
  type = 'button',
  ...props
}) {
  const base = 'inline-flex items-center justify-center font-semibold rounded-xl transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:ring-offset-gray-950 disabled:opacity-40 disabled:cursor-not-allowed'

  const variants = {
    primary: 'bg-brand-500 hover:bg-brand-600 text-white shadow-lg shadow-brand-500/20 active:scale-[0.98]',
    ghost:   'bg-transparent hover:bg-gray-800 text-gray-400 hover:text-gray-100 border border-gray-700 hover:border-gray-600',
  }

  const sizes = {
    sm: 'px-3.5 py-2 text-sm',
    md: 'px-5 py-2.5 text-sm',
    lg: 'px-7 py-3.5 text-base',
  }

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
