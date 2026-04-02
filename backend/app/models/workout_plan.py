"""
SQLAlchemy ORM model for the `workout_plans` table.

Each row represents one AI-generated workout plan, linked to the user who
requested it. The full Groq response is stored as JSON so the frontend can
replay any historical plan without re-calling the AI.
"""

from datetime import datetime

from sqlalchemy import Integer, String, ForeignKey, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkoutPlanRecord(Base):
    """
    Persisted workout plan produced by the AI generation endpoint.

    Table: workout_plans
    Columns:
      id            — auto-increment primary key
      user_id       — FK → users.id (CASCADE delete: remove plans when user is deleted)
      goal          — fitness goal string, e.g. "build_muscle"
      fitness_level — e.g. "beginner"
      days_per_week — number of training days requested
      plan_json     — the complete WorkoutPlan dict returned by Groq
      created_at    — UTC timestamp set by the database on INSERT
    """

    __tablename__ = "workout_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,        # speeds up history queries filtered by user
    )

    goal: Mapped[str] = mapped_column(String(50), nullable=False)

    fitness_level: Mapped[str] = mapped_column(String(50), nullable=False)

    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)

    # Stores the full nested plan dict (title, summary, days[], general_tips[])
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Convenience back-reference to the owning user (not required for queries,
    # but useful for future features like "user.workout_plans")
    user = relationship("User", back_populates="workout_plans")

    def __repr__(self) -> str:
        return (
            f"<WorkoutPlanRecord id={self.id} user_id={self.user_id} "
            f"goal={self.goal!r} created_at={self.created_at}>"
        )
