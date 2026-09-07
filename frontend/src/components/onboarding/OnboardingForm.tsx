import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronLeft } from 'lucide-react'

import Button from '../ui/Button'
import ProgressBar from '../ui/ProgressBar'
import Step1Personal from './steps/Step1Personal'
import Step2Goals from './steps/Step2Goals'
import Step3Level from './steps/Step3Level'
import Step4Equipment from './steps/Step4Equipment'
import Step5Schedule from './steps/Step5Schedule'
import {
  INITIAL_DRAFT,
  toOnboardingData,
  type OnboardingDraft,
  type StepProps,
} from './types'
import type { OnboardingData } from '../../schemas/api'

interface Step {
  id: number
  title: string
  component: (props: StepProps) => JSX.Element
  /** Whether the draft satisfies this step's requirements. */
  isComplete: (data: OnboardingDraft) => boolean
}

const MIN_AGE = 13

/**
 * Steps own their own completion rule instead of a switch keyed on the current
 * index. Reordering or inserting a step used to require editing that switch in
 * lockstep, and getting it wrong silently gated the wrong field.
 */
const STEPS: Step[] = [
  {
    id: 1,
    title: "Let's meet you",
    component: Step1Personal,
    isComplete: (d) => d.name.trim().length > 0 && d.age !== '' && d.age >= MIN_AGE,
  },
  {
    id: 2,
    title: 'Your goal',
    component: Step2Goals,
    isComplete: (d) => d.fitness_goal !== '',
  },
  {
    id: 3,
    title: 'Fitness level',
    component: Step3Level,
    isComplete: (d) => d.fitness_level !== '',
  },
  {
    id: 4,
    title: 'Your equipment',
    component: Step4Equipment,
    isComplete: (d) => d.available_equipment.length > 0,
  },
  {
    id: 5,
    title: 'Your schedule',
    component: Step5Schedule,
    isComplete: (d) => d.days_per_week >= 1,
  },
]

export interface OnboardingFormProps {
  /** Receives a validated payload — never a raw draft. */
  onSubmit: (data: OnboardingData) => void
  isLoading?: boolean
}

/**
 * Multi-step onboarding form container.
 *
 * Manages step navigation and accumulated draft state. Each child step receives
 * `data` and `onChange` so it stays fully controlled from here.
 */
export default function OnboardingForm({ onSubmit, isLoading = false }: OnboardingFormProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [draft, setDraft] = useState<OnboardingDraft>(INITIAL_DRAFT)
  const [direction, setDirection] = useState<1 | -1>(1)
  const [validationError, setValidationError] = useState<string | null>(null)

  const step = STEPS[currentStep]
  if (!step) throw new Error(`Onboarding step ${currentStep} does not exist`)

  const StepComponent = step.component
  const isLastStep = currentStep === STEPS.length - 1
  const progress = ((currentStep + 1) / STEPS.length) * 100

  const handleChange = (partial: Partial<OnboardingDraft>): void => {
    setDraft((prev) => ({ ...prev, ...partial }))
    setValidationError(null)
  }

  const goNext = (): void => {
    if (!isLastStep) {
      setDirection(1)
      setCurrentStep((s) => s + 1)
      return
    }

    // Final gate: the per-step checks are UI affordances, so the draft is
    // validated against the real schema before it becomes a request.
    const result = toOnboardingData(draft)
    if (!result.ok) {
      setValidationError(result.message)
      return
    }
    onSubmit(result.data)
  }

  const goBack = (): void => {
    setDirection(-1)
    setCurrentStep((s) => s - 1)
  }

  const variants = {
    enter: (dir: number) => ({ x: dir > 0 ? 40 : -40, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (dir: number) => ({ x: dir > 0 ? -40 : 40, opacity: 0 }),
  }

  return (
    <div className="w-full max-w-lg">
      {/* Step indicator */}
      <div className="mb-2 flex items-center justify-between text-sm text-gray-500">
        <span>
          Step {currentStep + 1} of {STEPS.length}
        </span>
        <span className="text-gray-400 font-medium">{step.title}</span>
      </div>

      <ProgressBar value={progress} className="mb-8" />

      {/* Animated step content */}
      <div className="card p-8 min-h-[340px] flex flex-col justify-between">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={currentStep}
            custom={direction}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="flex-1"
          >
            <StepComponent data={draft} onChange={handleChange} />
          </motion.div>
        </AnimatePresence>

        {validationError && (
          <p role="alert" className="mt-4 text-sm text-red-400">
            {validationError}
          </p>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between mt-8 pt-6 border-t border-gray-800">
          {currentStep > 0 ? (
            <Button variant="ghost" size="sm" onClick={goBack} disabled={isLoading}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              Back
            </Button>
          ) : (
            <div />
          )}

          <Button onClick={goNext} disabled={!step.isComplete(draft) || isLoading} size="md">
            {isLastStep ? 'Generate My Plan' : 'Continue'}
          </Button>
        </div>
      </div>
    </div>
  )
}
