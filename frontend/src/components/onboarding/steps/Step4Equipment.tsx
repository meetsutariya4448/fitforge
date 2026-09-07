import { Check } from 'lucide-react'

import type { Equipment } from '../../../schemas/api'
import type { StepProps } from '../types'

interface EquipmentOption {
  value: Equipment
  label: string
  emoji: string
  description: string
}

const EQUIPMENT_OPTIONS: EquipmentOption[] = [
  { value: 'no_equipment',     label: 'No Equipment',     emoji: '🏠', description: 'Bodyweight only' },
  { value: 'dumbbells',        label: 'Dumbbells',        emoji: '🏋️', description: 'Fixed or adjustable' },
  { value: 'barbell',          label: 'Barbell',          emoji: '🔩', description: 'With weight plates' },
  { value: 'resistance_bands', label: 'Resistance Bands', emoji: '🟡', description: 'Light to heavy bands' },
  { value: 'pull_up_bar',      label: 'Pull-up Bar',      emoji: '🔝', description: 'Doorframe or wall mounted' },
  { value: 'kettlebell',       label: 'Kettlebell',       emoji: '⚫', description: 'Single or multiple' },
  { value: 'full_gym',         label: 'Full Gym',         emoji: '🏟️', description: 'Access to all machines' },
]

/**
 * Step 4 — Select available equipment (multi-select).
 *
 * "No Equipment" is mutually exclusive with everything else in both
 * directions: picking it clears the rest, and picking anything else drops it.
 */
export default function Step4Equipment({ data, onChange }: StepProps) {
  const selected = data.available_equipment

  const toggle = (value: Equipment): void => {
    if (value === 'no_equipment') {
      onChange({
        available_equipment: selected.includes('no_equipment') ? [] : ['no_equipment'],
      })
      return
    }

    const next = selected.includes(value)
      ? selected.filter((v) => v !== value)
      : [...selected.filter((v) => v !== 'no_equipment'), value]

    onChange({ available_equipment: next })
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-1">What equipment do you have?</h2>
      <p className="text-gray-400 mb-6 text-sm">Select all that apply — you can choose multiple.</p>

      <div className="grid grid-cols-2 gap-2.5">
        {EQUIPMENT_OPTIONS.map((item) => {
          const isSelected = selected.includes(item.value)
          return (
            <button
              key={item.value}
              type="button"
              role="checkbox"
              aria-checked={isSelected}
              onClick={() => toggle(item.value)}
              className={`
                relative flex flex-col gap-1 px-3 py-3 rounded-xl border text-left
                transition-all duration-150
                ${isSelected
                  ? 'bg-brand-500/10 border-brand-500'
                  : 'bg-gray-800/50 border-gray-700 hover:border-gray-600'
                }
              `}
            >
              {isSelected && (
                <span className="absolute top-2 right-2 bg-brand-500 text-white rounded-full p-0.5">
                  <Check className="w-3 h-3" />
                </span>
              )}
              <span className="text-xl" aria-hidden="true">{item.emoji}</span>
              <span className={`text-sm font-medium ${isSelected ? 'text-white' : 'text-gray-300'}`}>
                {item.label}
              </span>
              <span className="text-xs text-gray-500">{item.description}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
