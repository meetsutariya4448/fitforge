"""
Workout sessions router.

POST /api/sessions              — log a new workout session
GET  /api/sessions              — list all sessions for the current user
GET  /api/sessions/{session_id} — get one session (must belong to current user)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.workout_session import WorkoutSession, ExerciseLog
from app.schemas.workout import SessionCreate, SessionResponse
from app.services.auth_service import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


# ── POST /api/sessions ────────────────────────────────────────────────────────

@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a new workout session",
)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new WorkoutSession for the authenticated user, along with all
    ExerciseLog rows supplied in the request body.
    """
    session = WorkoutSession(
        user_id=current_user.id,
        plan_id=payload.plan_id,
        day_name=payload.day_name,
        notes=payload.notes,
    )
    db.add(session)
    db.flush()   # get session.id without committing yet

    for log in payload.exercise_logs:
        db.add(ExerciseLog(
            session_id=session.id,
            exercise_name=log.exercise_name,
            sets_completed=log.sets_completed,
            reps_completed=log.reps_completed,
            weight_kg=log.weight_kg,
        ))

    db.commit()
    db.refresh(session)

    logger.info(
        "Logged session id=%d for user_id=%d (%d exercises)",
        session.id, current_user.id, len(payload.exercise_logs),
    )
    return session


# ── GET /api/sessions ─────────────────────────────────────────────────────────

@router.get(
    "/sessions",
    response_model=list[SessionResponse],
    summary="Get all workout sessions for the current user",
)
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all sessions for the authenticated user, newest first."""
    return (
        db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == current_user.id)
        .order_by(WorkoutSession.session_date.desc())
        .all()
    )


# ── GET /api/sessions/{session_id} ───────────────────────────────────────────

@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="Get a single session by ID",
)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return one session with its exercise logs.
    Returns 404 if the session doesn't exist, 403 if it belongs to another user.
    """
    session = db.get(WorkoutSession, session_id)

    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return session
