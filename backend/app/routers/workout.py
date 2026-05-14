"""
Workout router.

POST /api/workout/generate
  Generates a personalised workout plan via Groq AI, saves it to the
  database linked to the authenticated user, and returns the plan.
  Response shape is unchanged from the unauthenticated version.

GET /api/workout/history
  Returns all saved workout plans for the authenticated user,
  ordered by created_at descending (newest first).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.workout_plan import WorkoutPlanRecord
from app.schemas.workout import (
    OnboardingData,
    WorkoutPlanResponse,
    WorkoutHistoryResponse,
    WorkoutPlanHistoryItem,
)
from app.services.claude_service import generate_workout_plan
from app.services.auth_service import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


# ── POST /generate ────────────────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=WorkoutPlanResponse,
    summary="Generate a personalised workout plan",
    description=(
        "Accepts user onboarding data (name, age, goal, level, equipment, "
        "days per week) and uses Groq AI to produce a structured weekly "
        "workout plan tailored to the individual. The plan is saved to the "
        "database and linked to the authenticated user."
    ),
    status_code=status.HTTP_200_OK,
)
async def generate_plan(
    data: OnboardingData,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Steps:
      1. Validate incoming OnboardingData (Pydantic handles this automatically)
      2. Call Groq AI to generate the structured plan
      3. Persist the plan to workout_plans table linked to current_user
      4. Return the plan — same response shape as before
    """
    # ── Step 2: AI generation ─────────────────────────────────────────────────
    try:
        plan = await generate_workout_plan(data, session_history=data.session_history)

    except ValueError as exc:
        logger.warning("Plan generation schema error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI returned an unexpected response format. Please try again. ({exc})",
        ) from exc

    except Exception as exc:
        logger.error("Unexpected error during plan generation: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating your plan. Please try again.",
        ) from exc

    # ── Step 3: Persist to database ───────────────────────────────────────────
    # plan.model_dump() converts the Pydantic WorkoutPlan to a plain dict
    # that PostgreSQL's JSON column can store directly.
    record = WorkoutPlanRecord(
        user_id=current_user.id,
        goal=data.fitness_goal.value,
        fitness_level=data.fitness_level.value,
        days_per_week=data.days_per_week,
        plan_json=plan.model_dump(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info(
        "Saved workout plan id=%d for user_id=%d (goal=%s)",
        record.id, current_user.id, record.goal,
    )

    # ── Step 4: Return — identical shape to the original endpoint ─────────────
    return WorkoutPlanResponse(success=True, plan=plan)


# ── GET /history ──────────────────────────────────────────────────────────────

@router.get(
    "/history",
    response_model=WorkoutHistoryResponse,
    summary="Get the authenticated user's workout plan history",
    description=(
        "Returns all workout plans previously generated for the logged-in "
        "user, ordered newest-first. Each entry includes the full plan JSON "
        "so the frontend can replay any past plan without calling the AI again."
    ),
    status_code=status.HTTP_200_OK,
)
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetches all WorkoutPlanRecord rows belonging to current_user,
    ordered by created_at descending.
    """
    records = (
        db.query(WorkoutPlanRecord)
        .filter(WorkoutPlanRecord.user_id == current_user.id)
        .order_by(WorkoutPlanRecord.created_at.desc())
        .all()
    )

    items = [WorkoutPlanHistoryItem.model_validate(r) for r in records]

    return WorkoutHistoryResponse(plans=items, total=len(items))
