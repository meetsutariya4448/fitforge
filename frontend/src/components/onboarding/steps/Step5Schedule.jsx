/**
 * Step 5 — Choose days per week + optional notes.
 */
export default function Step5Schedule({ data, onChange }) {
  const days = [1, 2, 3, 4, 5, 6, 7]

  const descriptions = {
    1: 'Great for busy schedules or beginners',
    2: 'Good starting point for most beginners',
    3: 'Optimal for beginners and intermediate athletes',
    4: 'Solid split for intermediate to advanced',
    5: 'High volume — for dedicated athletes',
    6: 'Serious training with minimal rest days',
    7: 'Elite level — active recovery required',
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-1">How many days per week?</h2>
      <p className="text-gray-400 mb-6 text-sm">
        Your plan will be structured around your availability.
      </p>

      {/* Day selector */}
      <div className="flex gap-2 mb-3">
        {days.map((d) => {
          const isSelected = data.days_per_week === d
          return (
            <button
              key={d}
              onClick={() => onChange({ days_per_week: d })}
              className={`
                flex-1 py-3 rounded-xl border font-semibold text-sm
                transition-all duration-150
                ${isSelected
                  ? 'bg-brand-500 border-brand-500 text-white shadow-lg shadow-brand-500/20'
                  : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-600'
                }
              `}
            >
              {d}
            </button>
          )
        })}
      </div>

      <p className="text-xs text-gray-500 mb-8">
        {descriptions[data.days_per_week]}
      </p>

      {/* Optional notes */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Anything else we should know?{' '}
          <span className="text-gray-500 font-normal">(optional)</span>
        </label>
        <textarea
          value={data.additional_notes}
          onChange={(e) => onChange({ additional_notes: e.target.value })}
          placeholder="e.g. I have a bad knee, prefer mornings, avoid jump exercises…"
          rows={3}
          maxLength={500}
          className="input resize-none"
        />
        <p className="text-xs text-gray-600 mt-1 text-right">
          {data.additional_notes?.length || 0} / 500
        </p>
      </div>
    </div>
  )
}
