"""
Idempotent demo-user seed script.

Creates:
  - Demo user: demo@fitforge.app / Demo1234! / "Demo User"
  - 5 workout sessions across the past 4 weeks with exercise logs
  - Personal records are auto-computed from the session data

Run from the backend/ directory:
  python -m scripts.seed_demo
"""

import sys
import os
from datetime import datetime, timedelta, timezone

# Allow running from backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user import User
from app.models.workout_session import WorkoutSession, ExerciseLog
from app.models.personal_record import PersonalRecord
from app.services.auth_service import hash_password

DEMO_EMAIL = "demo@fitforge.app"
DEMO_PASSWORD = "Demo1234!"
DEMO_NAME = "Demo User"

# 5 sessions spread over the last 4 weeks
SESSIONS = [
    {
        "day_name": "Day 1 — Upper Body Push",
        "days_ago": 28,
        "exercises": [
            {"name": "Bench Press",      "sets": 4, "reps": 8,  "weight_kg": 60.0},
            {"name": "Overhead Press",   "sets": 3, "reps": 10, "weight_kg": 40.0},
            {"name": "Tricep Pushdown",  "sets": 3, "reps": 12, "weight_kg": 20.0},
        ],
    },
    {
        "day_name": "Day 2 — Lower Body",
        "days_ago": 25,
        "exercises": [
            {"name": "Barbell Squat",    "sets": 4, "reps": 6,  "weight_kg": 80.0},
            {"name": "Romanian Deadlift","sets": 3, "reps": 8,  "weight_kg": 70.0},
            {"name": "Leg Press",        "sets": 3, "reps": 12, "weight_kg": 100.0},
        ],
    },
    {
        "day_name": "Day 1 — Upper Body Push",
        "days_ago": 14,
        "exercises": [
            {"name": "Bench Press",      "sets": 4, "reps": 8,  "weight_kg": 65.0},
            {"name": "Overhead Press",   "sets": 3, "reps": 10, "weight_kg": 42.5},
            {"name": "Tricep Pushdown",  "sets": 3, "reps": 12, "weight_kg": 22.5},
        ],
    },
    {
        "day_name": "Day 2 — Lower Body",
        "days_ago": 11,
        "exercises": [
            {"name": "Barbell Squat",    "sets": 4, "reps": 6,  "weight_kg": 85.0},
            {"name": "Romanian Deadlift","sets": 3, "reps": 8,  "weight_kg": 75.0},
            {"name": "Leg Press",        "sets": 3, "reps": 12, "weight_kg": 110.0},
        ],
    },
    {
        "day_name": "Day 3 — Pull Day",
        "days_ago": 4,
        "exercises": [
            {"name": "Pull-Ups",         "sets": 4, "reps": 8,  "weight_kg": None},
            {"name": "Barbell Row",      "sets": 4, "reps": 8,  "weight_kg": 60.0},
            {"name": "Bicep Curl",       "sets": 3, "reps": 12, "weight_kg": 15.0},
            {"name": "Bench Press",      "sets": 1, "reps": 5,  "weight_kg": 70.0},  # new bench PR
        ],
    },
]


def seed():
    db = SessionLocal()
    try:
        # ── Demo user ─────────────────────────────────────────────────────────
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if user is None:
            user = User(
                name=DEMO_NAME,
                email=DEMO_EMAIL,
                hashed_password=hash_password(DEMO_PASSWORD),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"✅ Created demo user  id={user.id}  email={DEMO_EMAIL}")
        else:
            print(f"ℹ️  Demo user already exists  id={user.id}  email={DEMO_EMAIL}")

        # ── Workout sessions ──────────────────────────────────────────────────
        existing_count = (
            db.query(WorkoutSession)
            .filter(WorkoutSession.user_id == user.id)
            .count()
        )
        if existing_count >= len(SESSIONS):
            print(f"ℹ️  Demo sessions already seeded ({existing_count} sessions found) — skipping")
        else:
            now = datetime.now(timezone.utc)
            for s in SESSIONS:
                session_date = now - timedelta(days=s["days_ago"])
                ws = WorkoutSession(
                    user_id=user.id,
                    session_date=session_date,
                    day_name=s["day_name"],
                )
                db.add(ws)
                db.flush()

                for ex in s["exercises"]:
                    db.add(ExerciseLog(
                        session_id=ws.id,
                        exercise_name=ex["name"],
                        sets_completed=ex["sets"],
                        reps_completed=ex["reps"],
                        weight_kg=ex["weight_kg"],
                    ))

            db.commit()
            print(f"✅ Seeded {len(SESSIONS)} workout sessions")

        # ── Personal records ──────────────────────────────────────────────────
        pr_count = (
            db.query(PersonalRecord)
            .filter(PersonalRecord.user_id == user.id)
            .count()
        )
        if pr_count > 0:
            print(f"ℹ️  PRs already exist ({pr_count} records) — skipping")
        else:
            # Compute PRs from all exercise logs for this user
            logs = (
                db.query(ExerciseLog, WorkoutSession.session_date)
                .join(WorkoutSession, ExerciseLog.session_id == WorkoutSession.id)
                .filter(WorkoutSession.user_id == user.id)
                .all()
            )

            pr_map: dict[str, dict] = {}
            for log, session_date in logs:
                name = log.exercise_name
                if name not in pr_map:
                    pr_map[name] = {
                        "max_weight_kg": log.weight_kg,
                        "max_reps": log.reps_completed,
                        "achieved_at": session_date,
                    }
                else:
                    existing = pr_map[name]
                    if log.weight_kg is not None and (
                        existing["max_weight_kg"] is None or log.weight_kg > existing["max_weight_kg"]
                    ):
                        existing["max_weight_kg"] = log.weight_kg
                        existing["achieved_at"] = session_date
                    if log.reps_completed > (existing["max_reps"] or 0):
                        existing["max_reps"] = log.reps_completed

            for exercise_name, pr_data in pr_map.items():
                db.add(PersonalRecord(
                    user_id=user.id,
                    exercise_name=exercise_name,
                    max_weight_kg=pr_data["max_weight_kg"],
                    max_reps=pr_data["max_reps"],
                    achieved_at=pr_data["achieved_at"],
                ))

            db.commit()
            print(f"✅ Seeded {len(pr_map)} personal records")

        print("\n🏋️  Demo seed complete!")
        print(f"   Email:    {DEMO_EMAIL}")
        print(f"   Password: {DEMO_PASSWORD}")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
