"""
Pydantic schemas for user-related data.
These are the request/response models — not SQLAlchemy ORM models.
"""

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """Payload for creating a new account."""
    email: EmailStr
    password: str = Field(min_length=8, description="Minimum 8 characters")
    name: str = Field(min_length=1, max_length=100)


class UserLogin(BaseModel):
    """Payload for authenticating an existing user."""
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """Safe user representation returned to the client (no password)."""
    id: int
    email: str
    name: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT token returned after successful login/register."""
    access_token: str
    token_type: str = "bearer"
    user: UserOut
