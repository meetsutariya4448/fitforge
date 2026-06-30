"""
Workout sessions router.

POST /api/sessions                          — log a new workout session (auto-upserts PRs)
GET  /api/sessions                          — list all sessions for the current user
GET  /api/sessions/exercise/{exercise_name} — per-exercise strength trend data
GET  /api/sessions/{session_id}             — get one session (must belong to current user)
GET  /api/prs                               — get all personal records for current user
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.workout_session import WorkoutSession, ExerciseLog
from app.models.personal_record import PersonalRecord
from app.schemas.workout import (
    SessionCreate, SessionResponse,
    PROut, ExerciseTrendPoint, ExerciseTrendResponse,
)
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
    Create a new WorkoutSession + ExerciseLogs, then upsert personal records
    for any exercise where the logged weight or reps beats the stored PR.
    """
    session = WorkoutSession(
        user_id=current_user.id,
        plan_id=payload.plan_id,
        day_name=payload.day_name,
        notes=payload.notes,
    )
    db.add(session)
    db.flush()

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

    # ── Upsert personal records ───────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    for log in payload.exercise_logs:
        pr = (
            db.query(PersonalRecord)
            .filter(
                PersonalRecord.user_id == current_user.id,
                PersonalRecord.exercise_name == log.exercise_name,
            )
            .first()
        )

        if pr is None:
            # First time logging this exercise — create a PR record
            db.add(PersonalRecord(
                user_id=current_user.id,
                exercise_name=log.exercise_name,
                max_weight_kg=log.weight_kg,
                max_reps=log.reps_completed,
                achieved_at=now,
            ))
        else:
            updated = False
            # Update weight PR
            if log.weight_kg is not None:
                if pr.max_weight_kg is None or log.weight_kg > pr.max_weight_kg:
                    pr.max_weight_kg = log.weight_kg
                    updated = True
            # Update reps PR (for bodyweight or when reps beat old record)
            if log.reps_completed > (pr.max_reps or 0):
                pr.max_reps = log.reps_completed
                updated = True
            if updated:
                pr.achieved_at = now

    db.commit()

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


# ── GET /api/sessions/exercise/{exercise_name} ────────────────────────────────
# IMPORTANT: this literal route must be defined BEFORE /{session_id} so FastAPI
# doesn't try to cast "exercise" as an integer.

@router.get(
    "/sessions/exercise/{exercise_name}",
    response_model=ExerciseTrendResponse,
    summary="Get strength trend data for one exercise",
)
def get_exercise_trend(
    exercise_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all logged entries for the given exercise, sorted oldest→newest,
    so the frontend can plot a strength trend line chart.

    Each point includes the session date, max weight used, and total volume
    (sets × reps × weight_kg) for that log entry.
    """
    logs = (
        db.query(ExerciseLog, WorkoutSession.session_date)
        .join(WorkoutSession, ExerciseLog.session_id == WorkoutSession.id)
        .filter(
            WorkoutSession.user_id == current_user.id,
            ExerciseLog.exercise_name == exercise_name,
        )
        .order_by(WorkoutSession.session_date.asc())
        .all()
    )

    data = [
        ExerciseTrendPoint(
            date=session_date,
            max_weight_kg=log.weight_kg,
            total_volume=log.sets_completed * log.reps_completed * (log.weight_kg or 0),
        )
        for log, session_date in logs
    ]

    return ExerciseTrendResponse(exercise_name=exercise_name, data=data)


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
    """Return one session with its exercise logs. 404 if missing, 403 if wrong user."""
    session = db.get(WorkoutSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return session


# ── GET /api/prs ──────────────────────────────────────────────────────────────

@router.get(
    "/prs",
    response_model=list[PROut],
    summary="Get all personal records for the current user",
)
def list_prs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all PRs for the authenticated user, sorted by exercise name."""
    return (
        db.query(PersonalRecord)
        .filter(PersonalRecord.user_id == current_user.id)
        .order_by(PersonalRecord.exercise_name.asc())
        .all()
    )
