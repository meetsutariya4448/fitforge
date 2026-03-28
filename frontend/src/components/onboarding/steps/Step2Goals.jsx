import { Target, Flame, Wind, Leaf, Activity } from 'lucide-react'

const GOALS = [
  { value: 'lose_weight',           label: 'Lose Weight',           icon: <Flame className="w-5 h-5" />,    description: 'Burn fat and improve body composition' },
  { value: 'build_muscle',          label: 'Build Muscle',          icon: <Target className="w-5 h-5" />,   description: 'Increase strength and muscle size' },
  { value: 'improve_endurance',     label: 'Improve Endurance',     icon: <Wind className="w-5 h-5" />,     description: 'Boost cardiovascular fitness and stamina' },
  { value: 'increase_flexibility',  label: 'Increase Flexibility',  icon: <Leaf className="w-5 h-5" />,     description: 'Improve mobility and reduce injury risk' },
  { value: 'general_fitness',       label: 'General Fitness',       icon: <Activity className="w-5 h-5" />, description: 'Stay active and feel great overall' },
]

/**
 * Step 2 — Select a primary fitness goal.
 */
export default function Step2Goals({ data, onChange }) {
  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-1">What's your primary goal?</h2>
      <p className="text-gray-400 mb-6 text-sm">Your plan will be optimised around this.</p>

      <div className="space-y-3">
        {GOALS.map((goal) => {
          const isSelected = data.fitness_goal === goal.value
          return (
            <button
              key={goal.value}
              onClick={() => onChange({ fitness_goal: goal.value })}
              className={`
                w-full flex items-center gap-4 px-4 py-3.5 rounded-xl border text-left
                transition-all duration-150
                ${isSelected
                  ? 'bg-brand-500/10 border-brand-500 text-white'
                  : 'bg-gray-800/50 border-gray-700 text-gray-300 hover:border-gray-600'
                }
              `}
            >
              <span className={isSelected ? 'text-brand-500' : 'text-gray-500'}>
                {goal.icon}
              </span>
              <div>
                <div className="font-medium text-sm">{goal.label}</div>
                <div className="text-xs text-gray-500 mt-0.5">{goal.description}</div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
