"""
Workout router.

POST /api/workout/generate
  Generates a personalised workout plan via Groq AI, saves it to the
  database linked to the authenticated user, and returns the plan.

GET /api/workout/history
  Returns all saved workout plans for the authenticated user,
  ordered by created_at descending (newest first).
"""

import logging

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.models.workout_plan import WorkoutPlanRecord
from app.schemas.workout import (
    OnboardingData,
    WorkoutPlanResponse,
    WorkoutHistoryResponse,
    WorkoutPlanHistoryItem,
)
from app.services.ai_service import generate_workout_plan
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
@limiter.limit("20/minute")
async def generate_plan(
    request: Request,
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
        plan = await generate_workout_plan(data, session_history=data.session_history, db=db)

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
        "Returns workout plans newest-first, cursor-paginated. "
        "Pass ?cursor=<id> to fetch the next page. "
        "next_cursor in the response is null when no more pages exist."
    ),
    status_code=status.HTTP_200_OK,
)
def get_history(
    cursor: Optional[int] = Query(None, description="Return plans with id < cursor (for next-page fetches)"),
    limit: int = Query(20, ge=1, le=100, description="Plans per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        db.query(WorkoutPlanRecord)
        .filter(WorkoutPlanRecord.user_id == current_user.id)
    )
    if cursor is not None:
        q = q.filter(WorkoutPlanRecord.id < cursor)

    # Fetch limit+1 to detect whether a next page exists.
    records = q.order_by(WorkoutPlanRecord.id.desc()).limit(limit + 1).all()

    has_more = len(records) > limit
    page = records[:limit]
    next_cursor = page[-1].id if has_more and page else None

    # Total count for the current user (ignoring cursor, for UI display).
    total = db.query(WorkoutPlanRecord).filter(
        WorkoutPlanRecord.user_id == current_user.id
    ).count()

    return WorkoutHistoryResponse(
        plans=[WorkoutPlanHistoryItem.model_validate(r) for r in page],
        total=total,
        next_cursor=next_cursor,
    )


# ── POST /generate-agent ──────────────────────────────────────────────────────

@router.post(
    "/generate-agent",
    response_model=WorkoutPlanResponse,
    summary="Generate a workout plan via self-reflection agent",
    description=(
        "Runs a LangGraph critique loop on top of the RAG pipeline: "
        "retrieve → generate → critique → (refine → critique) × N. "
        "Returns the highest-scoring plan seen across all iterations. "
        "The existing /generate endpoint is unchanged."
    ),
    status_code=status.HTTP_200_OK,
)
@limiter.limit("10/minute")
async def generate_plan_agent(
    request: Request,
    data: OnboardingData,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.agent_service import run_agent
    try:
        plan = await run_agent(data, session_history=data.session_history, db=db)
    except ValueError as exc:
        logger.warning("Agent plan schema error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent returned an unexpected response format. ({exc})",
        ) from exc
    except Exception:
        logger.exception("Unexpected error in generate-agent")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred in the agent. Please try again.",
        )

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
        "Saved agent plan id=%d for user_id=%d (goal=%s)",
        record.id, current_user.id, record.goal,
    )

    return WorkoutPlanResponse(success=True, plan=plan)
