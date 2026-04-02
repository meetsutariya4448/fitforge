# Import all models here so that Base.metadata knows about them
# when create_all() is called at startup.
from app.models.user import User                    # noqa: F401
from app.models.workout_plan import WorkoutPlanRecord  # noqa: F401
