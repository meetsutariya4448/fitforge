/**
 * Runtime schemas for every FitForge API response the frontend consumes.
 *
 * TypeScript types describe what we *expect* at compile time; they disappear at
 * runtime and validate nothing. A renamed backend field, a null where a number
 * was promised, or an error page served by a proxy would all sail past the type
 * system and surface as an unrelated crash deep in a component. These schemas
 * are the actual guarantee: `services/api.ts` parses every response through them
 * at the boundary, so bad data fails once, loudly, with the field name in the
 * message.
 *
 * Types are derived from the schemas via z.infer rather than declared alongside
 * them, so a schema and its type cannot drift apart.
 *
 * Kept in sync with the FastAPI models in backend/app/schemas/ by
 * scripts/check-api-contract.mjs, which runs in CI.
 */

import { z } from 'zod'

// ── Primitives ────────────────────────────────────────────────────────────────

/**
 * FastAPI serialises datetimes as ISO 8601 strings. We keep them as strings
 * rather than coercing to Date: the values flow into chart libraries and
 * `new Date(...)` at the point of use, and an invalid date is far easier to
 * diagnose here than as a NaN axis three components later.
 */
const isoDateTime = z
  .string()
  .refine((v) => !Number.isNaN(Date.parse(v)), { message: 'not a parseable ISO datetime' })

// ── Errors ────────────────────────────────────────────────────────────────────

/**
 * Every error the API emits, including 429s, uses this envelope.
 * `code` is what callers branch on — notably REFRESH_RACE, which means the
 * session is healthy and another tab rotated first.
 */
export const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    retry_after: z.number().optional(),
    details: z.array(z.unknown()).optional(),
  }),
})

export type ApiError = z.infer<typeof apiErrorSchema>

// ── Auth ──────────────────────────────────────────────────────────────────────

export const userSchema = z.object({
  id: z.number(),
  email: z.string(),
  name: z.string(),
})

export const tokenResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.string().default('bearer'),
  user: userSchema,
})

export type User = z.infer<typeof userSchema>
export type TokenResponse = z.infer<typeof tokenResponseSchema>

// ── Onboarding (request) ──────────────────────────────────────────────────────

export const fitnessGoalSchema = z.enum([
  'lose_weight',
  'build_muscle',
  'improve_endurance',
  'increase_flexibility',
  'general_fitness',
])

export const fitnessLevelSchema = z.enum(['beginner', 'intermediate', 'advanced'])

export const equipmentSchema = z.enum([
  'no_equipment',
  'dumbbells',
  'barbell',
  'resistance_bands',
  'pull_up_bar',
  'kettlebell',
  'full_gym',
])

/**
 * Mirrors backend OnboardingData, bounds included. Validating the request
 * before it leaves the browser turns a 422 round-trip into an inline message.
 */
export const onboardingDataSchema = z.object({
  name: z.string().min(1).max(100),
  age: z.number().int().min(13).max(100),
  fitness_goal: fitnessGoalSchema,
  fitness_level: fitnessLevelSchema,
  available_equipment: z.array(equipmentSchema).min(1),
  days_per_week: z.number().int().min(1).max(7),
  additional_notes: z.string().max(500).nullish(),
  session_history: z.string().nullish(),
})

export type FitnessGoal = z.infer<typeof fitnessGoalSchema>
export type FitnessLevel = z.infer<typeof fitnessLevelSchema>
export type Equipment = z.infer<typeof equipmentSchema>
export type OnboardingData = z.infer<typeof onboardingDataSchema>

// ── Workout plan ──────────────────────────────────────────────────────────────

export const exerciseSchema = z.object({
  name: z.string(),
  // reps is a string on purpose — the model returns "8-12" or "30 seconds".
  sets: z.number().nullish(),
  reps: z.string().nullish(),
  rest_seconds: z.number().nullish(),
  notes: z.string().nullish(),
})

export const workoutDaySchema = z.object({
  day: z.string(),
  focus: z.string(),
  duration_minutes: z.number(),
  exercises: z.array(exerciseSchema),
  warmup_notes: z.string().nullish(),
  cooldown_notes: z.string().nullish(),
})

export const workoutPlanSchema = z.object({
  title: z.string(),
  summary: z.string(),
  days: z.array(workoutDaySchema),
  general_tips: z.array(z.string()),
  generated_for: z.string(),
  citations: z.array(z.string()).default([]),
  grounded: z.boolean().default(true),
})

export const workoutPlanResponseSchema = z.object({
  success: z.boolean(),
  plan: workoutPlanSchema,
})

export type Exercise = z.infer<typeof exerciseSchema>
export type WorkoutDay = z.infer<typeof workoutDaySchema>
export type WorkoutPlan = z.infer<typeof workoutPlanSchema>
export type WorkoutPlanResponse = z.infer<typeof workoutPlanResponseSchema>

// ── Plan history ──────────────────────────────────────────────────────────────

export const workoutPlanHistoryItemSchema = z.object({
  id: z.number(),
  goal: z.string(),
  fitness_level: z.string(),
  days_per_week: z.number(),
  created_at: isoDateTime,
  // Stored plans predate the current plan shape, so this is validated lazily:
  // a history list must still render when one old row cannot be parsed.
  plan_json: z.record(z.unknown()),
})

export const workoutHistoryResponseSchema = z.object({
  plans: z.array(workoutPlanHistoryItemSchema),
  total: z.number(),
  next_cursor: z.number().nullish(),
})

export type WorkoutPlanHistoryItem = z.infer<typeof workoutPlanHistoryItemSchema>
export type WorkoutHistoryResponse = z.infer<typeof workoutHistoryResponseSchema>

// ── Sessions ──────────────────────────────────────────────────────────────────

export const exerciseLogCreateSchema = z.object({
  exercise_name: z.string().min(1),
  sets_completed: z.number().int().nonnegative(),
  reps_completed: z.number().int().nonnegative(),
  weight_kg: z.number().nonnegative().nullish(),
})

export const sessionCreateSchema = z.object({
  day_name: z.string().min(1),
  plan_id: z.number().nullish(),
  notes: z.string().nullish(),
  exercise_logs: z.array(exerciseLogCreateSchema).min(1),
})

export const exerciseLogResponseSchema = z.object({
  id: z.number(),
  exercise_name: z.string(),
  sets_completed: z.number(),
  reps_completed: z.number(),
  // .nullable() not .nullish(): the API always sends this key, sometimes null.
  // Accepting its absence would let a removed field pass unnoticed.
  weight_kg: z.number().nullable(),
  created_at: isoDateTime,
})

export const sessionResponseSchema = z.object({
  id: z.number(),
  day_name: z.string(),
  plan_id: z.number().nullable(),
  notes: z.string().nullable(),
  session_date: isoDateTime,
  created_at: isoDateTime,
  exercise_logs: z.array(exerciseLogResponseSchema),
})

export const sessionListSchema = z.array(sessionResponseSchema)

export type ExerciseLogCreate = z.infer<typeof exerciseLogCreateSchema>
export type SessionCreate = z.infer<typeof sessionCreateSchema>
export type ExerciseLogResponse = z.infer<typeof exerciseLogResponseSchema>
export type SessionResponse = z.infer<typeof sessionResponseSchema>

// ── Personal records ──────────────────────────────────────────────────────────

export const prSchema = z.object({
  id: z.number(),
  exercise_name: z.string(),
  max_weight_kg: z.number().nullable(),
  max_reps: z.number().nullable(),
  achieved_at: isoDateTime,
})

export const prListSchema = z.array(prSchema)

export type PersonalRecord = z.infer<typeof prSchema>

// ── Exercise trend ────────────────────────────────────────────────────────────

export const exerciseTrendPointSchema = z.object({
  date: isoDateTime,
  max_weight_kg: z.number().nullable(),
  total_volume: z.number(),
})

export const exerciseTrendResponseSchema = z.object({
  exercise_name: z.string(),
  data: z.array(exerciseTrendPointSchema),
})

export type ExerciseTrendPoint = z.infer<typeof exerciseTrendPointSchema>
export type ExerciseTrendResponse = z.infer<typeof exerciseTrendResponseSchema>
