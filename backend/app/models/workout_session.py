"""
SQLAlchemy ORM models for workout session tracking.

WorkoutSession — one logged training session (a specific day's workout)
ExerciseLog    — one exercise entry within a session (sets/reps/weight)

Relationship: WorkoutSession has many ExerciseLogs (cascade delete).
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class WorkoutSession(Base):
    """
    A single logged workout session.

    Table: workout_sessions
    Links to the user who logged it and optionally to the plan it came from.
    """

    __tablename__ = "workout_sessions"

    id = Column(Integer, primary_key=True, index=True)

    # Which user logged this session
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Optional link back to the AI-generated plan this session follows
    plan_id = Column(Integer, ForeignKey("workout_plans.id"), nullable=True)

    # When the workout actually took place
    session_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Which day of the plan was performed, e.g. "Day 1", "Upper Body"
    day_name = Column(String, nullable=False)

    # Free-form notes about the session
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # One session has many exercise log entries
    exercise_logs = relationship(
        "ExerciseLog",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<WorkoutSession id={self.id} user_id={self.user_id} day={self.day_name!r}>"


class ExerciseLog(Base):
    """
    A single exercise entry within a workout session.

    Table: exercise_logs
    Stores actual performance data: sets, reps, and optional weight.
    """

    __tablename__ = "exercise_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Parent session
    session_id = Column(
        Integer,
        ForeignKey("workout_sessions.id"),
        nullable=False,
        index=True,
    )

    exercise_name = Column(String, nullable=False)
    sets_completed = Column(Integer, nullable=False)
    reps_completed = Column(Integer, nullable=False)
    weight_kg = Column(Float, nullable=True)   # null = bodyweight exercise

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("WorkoutSession", back_populates="exercise_logs")

    def __repr__(self) -> str:
        return (
            f"<ExerciseLog id={self.id} exercise={self.exercise_name!r} "
            f"sets={self.sets_completed} reps={self.reps_completed}>"
        )
