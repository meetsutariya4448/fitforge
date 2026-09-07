/**
 * Fail the build when the frontend's zod schemas drift from the FastAPI models.
 *
 * The zod schemas in src/schemas/api.ts are hand-written, which keeps them
 * readable but means nothing stops the backend renaming a field and the
 * frontend finding out in production. This compares them against the API's own
 * OpenAPI document — generated from the Pydantic models, so it is the backend's
 * own account of its shape, not a second hand-maintained copy.
 *
 * What it checks, per mapped schema:
 *   - every required backend field exists in the zod schema
 *   - no zod field is absent from the backend response
 *   - a field the backend marks required is not optional in zod
 *
 * What it deliberately does not check: exact type equality. `reps` is a string
 * holding "8-12", datetimes are ISO strings validated by a refinement, and
 * plan_json is an opaque blob — encoding those rules here would mean
 * reimplementing zod in this script. Field-level drift is the failure that
 * actually happens.
 *
 * Usage:  node scripts/check-api-contract.mjs <path-to-openapi.json>
 */

import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { resolve } from 'node:path'

const openApiPath = process.argv[2]
if (!openApiPath) {
  console.error('usage: node scripts/check-api-contract.mjs <path-to-openapi.json>')
  process.exit(2)
}

const schemasModuleUrl = pathToFileURL(resolve('src/schemas/api.ts')).href
const schemas = await import(schemasModuleUrl)

const openapi = JSON.parse(readFileSync(openApiPath, 'utf8'))
const components = openapi.components?.schemas ?? {}

/**
 * zod schema name (in src/schemas/api.ts) → OpenAPI component name.
 * Only response and request bodies the frontend actually parses are listed;
 * anything else is not a contract we depend on.
 */
const MAPPINGS = [
  ['userSchema', 'UserOut'],
  ['tokenResponseSchema', 'TokenResponse'],
  ['onboardingDataSchema', 'OnboardingData'],
  ['exerciseSchema', 'Exercise'],
  ['workoutDaySchema', 'WorkoutDay'],
  ['workoutPlanSchema', 'WorkoutPlan'],
  ['workoutPlanResponseSchema', 'WorkoutPlanResponse'],
  ['workoutPlanHistoryItemSchema', 'WorkoutPlanHistoryItem'],
  ['workoutHistoryResponseSchema', 'WorkoutHistoryResponse'],
  ['exerciseLogCreateSchema', 'ExerciseLogCreate'],
  ['sessionCreateSchema', 'SessionCreate'],
  ['exerciseLogResponseSchema', 'ExerciseLogResponse'],
  ['sessionResponseSchema', 'SessionResponse'],
  ['prSchema', 'PROut'],
  ['exerciseTrendPointSchema', 'ExerciseTrendPoint'],
  ['exerciseTrendResponseSchema', 'ExerciseTrendResponse'],
]

/** Unwrap ZodOptional/ZodNullable/ZodDefault down to the underlying type. */
function unwrap(schema) {
  let current = schema
  for (;;) {
    const typeName = current?._def?.typeName
    if (
      typeName === 'ZodOptional' ||
      typeName === 'ZodNullable' ||
      typeName === 'ZodDefault' ||
      typeName === 'ZodEffects'
    ) {
      current = current._def.innerType ?? current._def.schema
      continue
    }
    return current
  }
}

/** True when zod would accept the field being absent. */
function acceptsMissing(schema) {
  return schema.isOptional()
}

const failures = []

for (const [zodName, componentName] of MAPPINGS) {
  const zodSchema = schemas[zodName]
  const component = components[componentName]

  if (!zodSchema) {
    failures.push(`${zodName}: not exported from src/schemas/api.ts`)
    continue
  }
  if (!component) {
    failures.push(
      `${componentName}: not found in the OpenAPI document (renamed or removed?)`,
    )
    continue
  }

  const shape = unwrap(zodSchema)._def.shape?.()
  if (!shape) {
    failures.push(`${zodName}: not an object schema, cannot compare`)
    continue
  }

  const zodFields = new Set(Object.keys(shape))
  const backendFields = new Set(Object.keys(component.properties ?? {}))
  const backendRequired = new Set(component.required ?? [])

  for (const field of backendFields) {
    if (!zodFields.has(field)) {
      failures.push(`${componentName}.${field}: present in the API, missing from ${zodName}`)
    }
  }

  for (const field of zodFields) {
    if (!backendFields.has(field)) {
      failures.push(`${zodName}.${field}: declared in zod, absent from ${componentName}`)
    }
  }

  for (const field of backendRequired) {
    const zodField = shape[field]
    if (zodField && acceptsMissing(zodField)) {
      failures.push(
        `${componentName}.${field}: required by the API but optional in ${zodName}`,
      )
    }
  }
}

if (failures.length > 0) {
  console.error('\nAPI contract drift detected:\n')
  for (const failure of failures) console.error(`  ✗ ${failure}`)
  console.error(
    `\n${failures.length} mismatch(es). Update src/schemas/api.ts to match the backend, ` +
      'or update the backend if the frontend is right.\n',
  )
  process.exit(1)
}

console.log(`✓ ${MAPPINGS.length} schemas match the API contract`)
