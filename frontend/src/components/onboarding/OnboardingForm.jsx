import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import ProgressBar from '../ui/ProgressBar'
import Step1Personal from './steps/Step1Personal'
import Step2Goals from './steps/Step2Goals'
import Step3Level from './steps/Step3Level'
import Step4Equipment from './steps/Step4Equipment'
import Step5Schedule from './steps/Step5Schedule'
import Button from '../ui/Button'
import { ChevronLeft } from 'lucide-react'

const STEPS = [
  { id: 1, title: "Let's meet you",   component: Step1Personal },
  { id: 2, title: 'Your goal',         component: Step2Goals },
  { id: 3, title: 'Fitness level',     component: Step3Level },
  { id: 4, title: 'Your equipment',    component: Step4Equipment },
  { id: 5, title: 'Your schedule',     component: Step5Schedule },
]

const INITIAL_DATA = {
  name: '',
  age: '',
  fitness_goal: '',
  fitness_level: '',
  available_equipment: [],
  days_per_week: 3,
  additional_notes: '',
}

/**
 * Multi-step onboarding form container.
 *
 * Manages step navigation and accumulated form state. Each child step
 * component receives `data` (current values) and `onChange` (partial update)
 * so it can be fully controlled from here.
 *
 * @param {Function} onSubmit  - Called with complete form data when finished
 * @param {boolean}  isLoading - Disables the submit button while loading
 */
export default function OnboardingForm({ onSubmit, isLoading }) {
  const [currentStep, setCurrentStep] = useState(0)
  const [formData, setFormData] = useState(INITIAL_DATA)
  const [direction, setDirection] = useState(1) // 1 = forward, -1 = backward

  const StepComponent = STEPS[currentStep].component
  const isLastStep = currentStep === STEPS.length - 1
  const progress = ((currentStep + 1) / STEPS.length) * 100

  /** Merge partial updates into accumulated form data */
  const handleChange = (partial) => {
    setFormData((prev) => ({ ...prev, ...partial }))
  }

  const goNext = () => {
    if (isLastStep) {
      onSubmit(formData)
    } else {
      setDirection(1)
      setCurrentStep((s) => s + 1)
    }
  }

  const goBack = () => {
    setDirection(-1)
    setCurrentStep((s) => s - 1)
  }

  /** Validate current step before allowing next */
  const canProceed = () => {
    switch (currentStep) {
      case 0: return formData.name.trim() && formData.age >= 13
      case 1: return !!formData.fitness_goal
      case 2: return !!formData.fitness_level
      case 3: return formData.available_equipment.length > 0
      case 4: return formData.days_per_week >= 1
      default: return true
    }
  }

  const variants = {
    enter: (dir) => ({ x: dir > 0 ? 40 : -40, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (dir) => ({ x: dir > 0 ? -40 : 40, opacity: 0 }),
  }

  return (
    <div className="w-full max-w-lg">
      {/* Step indicator */}
      <div className="mb-2 flex items-center justify-between text-sm text-gray-500">
        <span>Step {currentStep + 1} of {STEPS.length}</span>
        <span className="text-gray-400 font-medium">{STEPS[currentStep].title}</span>
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
            <StepComponent data={formData} onChange={handleChange} />
          </motion.div>
        </AnimatePresence>

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

          <Button
            onClick={goNext}
            disabled={!canProceed() || isLoading}
            size="md"
          >
            {isLastStep ? 'Generate My Plan' : 'Continue'}
          </Button>
        </div>
      </div>
    </div>
  )
}
