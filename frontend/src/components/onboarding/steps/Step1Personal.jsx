/**
 * Step 1 — Collect user's name and age.
 */
export default function Step1Personal({ data, onChange }) {
  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-1">What's your name?</h2>
      <p className="text-gray-400 mb-8 text-sm">We'll personalise your plan just for you.</p>

      <div className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            First name
          </label>
          <input
            type="text"
            value={data.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="e.g. Alex"
            className="input"
            autoFocus
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Age
          </label>
          <input
            type="number"
            value={data.age}
            onChange={(e) => onChange({ age: Number(e.target.value) })}
            placeholder="e.g. 24"
            min={13}
            max={100}
            className="input"
          />
          <p className="text-xs text-gray-500 mt-1.5">Must be 13 or older</p>
        </div>
      </div>
    </div>
  )
}
