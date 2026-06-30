"""
Pydantic schemas for workout planning.

OnboardingData  → what the frontend sends to generate a plan
Exercise        → a single exercise within a day
WorkoutDay      → one day's worth of exercises
WorkoutPlan     → the full weekly plan returned to the frontend
"""

from datetime import datetime

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
    session_history: Optional[str] = Field(
        default=None,
        description="Summary of recent training sessions for context-aware plan generation"
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
    The complete weekly workout plan returned after AI generation.
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


# ── History schemas ───────────────────────────────────────────────────────────

class WorkoutPlanHistoryItem(BaseModel):
    """
    A single entry in the user's plan history.
    Returned by GET /api/workout/history — includes the full plan_json so
    the frontend can render any past plan without calling the AI again.
    """
    id: int
    goal: str
    fitness_level: str
    days_per_week: int
    created_at: datetime
    plan_json: dict

    model_config = {"from_attributes": True}


class WorkoutHistoryResponse(BaseModel):
    """Response for the history endpoint — ordered newest-first."""
    plans: List[WorkoutPlanHistoryItem]
    total: int


# ── Session schemas ───────────────────────────────────────────────────────────

class ExerciseLogCreate(BaseModel):
    """One exercise entry submitted when logging a session."""
    exercise_name: str
    sets_completed: int
    reps_completed: int
    weight_kg: Optional[float] = None


class SessionCreate(BaseModel):
    """Payload for POST /api/sessions — creates a new workout session."""
    day_name: str
    plan_id: Optional[int] = None
    notes: Optional[str] = None
    exercise_logs: List[ExerciseLogCreate]


class ExerciseLogResponse(BaseModel):
    """One exercise entry returned from the API."""
    id: int
    exercise_name: str
    sets_completed: int
    reps_completed: int
    weight_kg: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    """A full workout session with all its exercise logs."""
    id: int
    day_name: str
    plan_id: Optional[int]
    notes: Optional[str]
    session_date: datetime
    created_at: datetime
    exercise_logs: List[ExerciseLogResponse]

    class Config:
        from_attributes = True


# ── Personal Record schemas ───────────────────────────────────────────────────

class PROut(BaseModel):
    """One personal record entry returned from GET /api/prs."""
    id: int
    exercise_name: str
    max_weight_kg: Optional[float]
    max_reps: Optional[int]
    achieved_at: datetime

    class Config:
        from_attributes = True


# ── Exercise strength trend schemas ──────────────────────────────────────────

class ExerciseTrendPoint(BaseModel):
    """One data point in a per-exercise strength trend."""
    date: datetime
    max_weight_kg: Optional[float]
    total_volume: float     # sets * reps * weight_kg for that log entry


class ExerciseTrendResponse(BaseModel):
    """Response for GET /api/sessions/exercise/{exercise_name}."""
    exercise_name: str
    data: List[ExerciseTrendPoint]
