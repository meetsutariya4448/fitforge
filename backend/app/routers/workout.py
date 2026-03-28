"""
Workout router.

POST /api/workout/generate
  Accepts OnboardingData, calls the Claude service, and returns a WorkoutPlan.
"""

import logging
from fastapi import APIRouter, HTTPException, status

from app.schemas.workout import OnboardingData, WorkoutPlanResponse
from app.services.claude_service import generate_workout_plan

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/generate",
    response_model=WorkoutPlanResponse,
    summary="Generate a personalised workout plan",
    description=(
        "Accepts user onboarding data (name, age, goal, level, equipment, "
        "days per week) and uses Claude AI to produce a structured weekly "
        "workout plan tailored to the individual."
    ),
    status_code=status.HTTP_200_OK,
)
async def generate_plan(data: OnboardingData):
    """
    Main endpoint for Module 1 — AI Workout Planner.

    Steps:
      1. Validate incoming OnboardingData (Pydantic handles this automatically)
      2. Delegate to the Claude service for AI generation
      3. Return the structured WorkoutPlan wrapped in a success response
    """
    try:
        plan = await generate_workout_plan(data)
        return WorkoutPlanResponse(success=True, plan=plan)

    except ValueError as exc:
        # Schema / parsing errors from Claude's response
        logger.warning("Plan generation schema error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI returned an unexpected response format. Please try again. ({exc})",
        ) from exc

    except Exception as exc:
        # Covers Anthropic APIError and unexpected errors
        logger.error("Unexpected error during plan generation: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating your plan. Please try again.",
        ) from exc
