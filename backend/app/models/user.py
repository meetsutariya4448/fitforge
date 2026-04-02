"""
SQLAlchemy ORM model for the `users` table.

This is the database representation of a user.
The corresponding Pydantic schemas (for request/response) live in
app/schemas/user.py — keep these two layers separate.
"""

from datetime import datetime, timezone

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """
    Represents a registered FitForge user.

    Table: users
    Columns:
      id         — auto-increment primary key
      name       — display name (max 100 chars)
      email      — unique login identifier
      hashed_password — bcrypt hash, never the raw password
      created_at — UTC timestamp set automatically on insert
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),   # set by the DB on INSERT
        nullable=False,
    )

    # One-to-many: a user can have many saved workout plans
    workout_plans = relationship(
        "WorkoutPlanRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
