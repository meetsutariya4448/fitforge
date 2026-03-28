const LEVELS = [
  {
    value: 'beginner',
    label: 'Beginner',
    badge: '0–1 yr',
    description: "I'm just starting out or getting back into fitness after a long break.",
    color: 'text-green-400',
    borderColor: 'border-green-500',
    bgColor: 'bg-green-500/10',
  },
  {
    value: 'intermediate',
    label: 'Intermediate',
    badge: '1–3 yrs',
    description: 'I train consistently and know the basics of most exercises.',
    color: 'text-yellow-400',
    borderColor: 'border-yellow-500',
    bgColor: 'bg-yellow-500/10',
  },
  {
    value: 'advanced',
    label: 'Advanced',
    badge: '3+ yrs',
    description: "I've been training seriously for years and am ready for a real challenge.",
    color: 'text-red-400',
    borderColor: 'border-red-500',
    bgColor: 'bg-red-500/10',
  },
]

/**
 * Step 3 — Select fitness level.
 */
export default function Step3Level({ data, onChange }) {
  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-1">Your fitness level?</h2>
      <p className="text-gray-400 mb-6 text-sm">Be honest — the right intensity matters.</p>

      <div className="space-y-3">
        {LEVELS.map((level) => {
          const isSelected = data.fitness_level === level.value
          return (
            <button
              key={level.value}
              onClick={() => onChange({ fitness_level: level.value })}
              className={`
                w-full flex items-start gap-4 px-4 py-4 rounded-xl border text-left
                transition-all duration-150
                ${isSelected
                  ? `${level.bgColor} ${level.borderColor} text-white`
                  : 'bg-gray-800/50 border-gray-700 text-gray-300 hover:border-gray-600'
                }
              `}
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className={`font-semibold text-sm ${isSelected ? level.color : 'text-gray-200'}`}>
                    {level.label}
                  </span>
                  <span className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded-full">
                    {level.badge}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">{level.description}</p>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
