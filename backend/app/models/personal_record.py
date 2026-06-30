from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from app.database import Base


class PersonalRecord(Base):
    """
    Stores the all-time best performance for one (user, exercise) pair.

    Table: personal_records
    Updated automatically after every POST /api/sessions — if the new
    session's weight (or reps for bodyweight exercises) beats the stored
    record, the row is updated in-place.
    """

    __tablename__ = "personal_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    exercise_name = Column(String, nullable=False)
    max_weight_kg = Column(Float, nullable=True)   # null for bodyweight exercises
    max_reps = Column(Integer, nullable=True)
    achieved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # One user can have at most one PR per exercise
    __table_args__ = (
        UniqueConstraint("user_id", "exercise_name", name="uq_user_exercise_pr"),
    )

    def __repr__(self) -> str:
        return (
            f"<PersonalRecord user_id={self.user_id} exercise={self.exercise_name!r} "
            f"weight={self.max_weight_kg}kg reps={self.max_reps}>"
        )
