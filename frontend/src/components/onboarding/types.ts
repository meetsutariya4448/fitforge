/**
 * Types shared by the onboarding wizard and its step components.
 *
 * The wizard's working state is deliberately NOT `OnboardingData`. A form in
 * progress holds values the API would reject — an empty goal before the user
 * picks one, an age field the user has cleared — and typing the draft as the
 * request payload would either force lies (`as OnboardingData`) or push
 * placeholder values like age 0 into state. `OnboardingDraft` describes what a
 * half-filled form legitimately looks like; `toOnboardingData` is the one place
 * it becomes a validated payload.
 */

import {
  onboardingDataSchema,
  type Equipment,
  type FitnessGoal,
  type FitnessLevel,
  type OnboardingData,
} from '../../schemas/api'

export interface OnboardingDraft {
  name: string
  /** Empty string while the field is blank — number inputs yield '' when cleared. */
  age: number | ''
  fitness_goal: FitnessGoal | ''
  fitness_level: FitnessLevel | ''
  available_equipment: Equipment[]
  days_per_week: number
  additional_notes: string
}

export const INITIAL_DRAFT: OnboardingDraft = {
  name: '',
  age: '',
  fitness_goal: '',
  fitness_level: '',
  available_equipment: [],
  days_per_week: 3,
  additional_notes: '',
}

/** Props every step component receives from the wizard. */
export interface StepProps {
  data: OnboardingDraft
  onChange: (partial: Partial<OnboardingDraft>) => void
}

export type DraftValidation =
  | { ok: true; data: OnboardingData }
  | { ok: false; message: string }

/**
 * Validate a completed draft into a request payload.
 *
 * The per-step `canProceed` checks stop most bad input, but they are UI
 * affordances, not guarantees — a user can reach the last step and clear a
 * field. Running the same zod schema the API client uses means the wizard and
 * the request agree on what "valid" means.
 */
export function toOnboardingData(draft: OnboardingDraft): DraftValidation {
  const parsed = onboardingDataSchema.safeParse({
    name: draft.name.trim(),
    age: draft.age === '' ? undefined : draft.age,
    fitness_goal: draft.fitness_goal || undefined,
    fitness_level: draft.fitness_level || undefined,
    available_equipment: draft.available_equipment,
    days_per_week: draft.days_per_week,
    additional_notes: draft.additional_notes.trim() || null,
  })

  if (parsed.success) return { ok: true, data: parsed.data }

  const first = parsed.error.issues[0]
  const field = first?.path.join('.') ?? 'form'
  return { ok: false, message: `Please check the ${field} field: ${first?.message ?? 'invalid'}` }
}
