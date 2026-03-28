"""
Authentication router — stub for Module 1.

Full JWT auth (register / login / refresh) will be wired to the database
in Module 2. For now, these endpoints return 501 so the frontend can be
built against the correct URL shape without needing a live DB.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def auth_status():
    """Placeholder — confirms the auth router is mounted correctly."""
    return {"message": "Auth endpoints are coming in Module 2"}
