"""
Pydantic schemas for workout planning.

OnboardingData  → what the frontend sends to generate a plan
Exercise        → a single exercise within a day
WorkoutDay      → one day's worth of exercises
WorkoutPlan     → the full weekly plan returned to the frontend
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class FitnessGoal(str, Enum):
    LOSE_WEIGHT   = "lose_weight"
    BUILD_MUSCLE  = "build_muscle"
    IMPROVE_ENDURANCE = "improve_endurance"
    INCREASE_FLEXIBILITY = "increase_flexibility"
    GENERAL_FITNESS = "general_fitness"


class FitnessLevel(str, Enum):
    BEGINNER     = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED     = "advanced"


class Equipment(str, Enum):
    NO_EQUIPMENT  = "no_equipment"
    DUMBBELLS     = "dumbbells"
    BARBELL       = "barbell"
    RESISTANCE_BANDS = "resistance_bands"
    PULL_UP_BAR   = "pull_up_bar"
    KETTLEBELL    = "kettlebell"
    FULL_GYM      = "full_gym"


# ── Request schema ─────────────────────────────────────────────────────────────

class OnboardingData(BaseModel):
    """
    Data collected during the multi-step onboarding flow.
    Sent to POST /api/workout/generate to produce a personalised plan.
    """
    name: str = Field(min_length=1, max_length=100, description="User's first name")
    age: int = Field(ge=13, le=100, description="Age in years")
    fitness_goal: FitnessGoal
    fitness_level: FitnessLevel
    available_equipment: List[Equipment] = Field(
        min_length=1,
        description="At least one equipment option must be selected"
    )
    days_per_week: int = Field(ge=1, le=7, description="Training days per week")
    additional_notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Any injuries, preferences, or extra context"
    )


# ── Response schemas ──────────────────────────────────────────────────────────

class Exercise(BaseModel):
    """A single exercise within a workout day."""
    name: str
    sets: Optional[int] = None
    reps: Optional[str] = None      # Can be "8-12" or "30 seconds" etc.
    rest_seconds: Optional[int] = None
    notes: Optional[str] = None     # Form tips, modifications, etc.


class WorkoutDay(BaseModel):
    """All exercises for one training day."""
    day: str                         # e.g. "Monday", "Day 1"
    focus: str                       # e.g. "Upper Body Strength"
    duration_minutes: int
    exercises: List[Exercise]
    warmup_notes: Optional[str] = None
    cooldown_notes: Optional[str] = None


class WorkoutPlan(BaseModel):
    """
    The complete weekly workout plan returned after Claude generation.
    Structured so the frontend can render collapsible day cards.
    """
    title: str                       # e.g. "4-Day Intermediate Muscle Building Plan"
    summary: str                     # 2-3 sentence overview
    days: List[WorkoutDay]
    general_tips: List[str]          # Nutrition, recovery, progression advice
    generated_for: str               # Echo back the user's name


class WorkoutPlanResponse(BaseModel):
    """API response wrapper around WorkoutPlan."""
    success: bool = True
    plan: WorkoutPlan
