"""
Authentication router.

Endpoints:
  POST /api/auth/register  — create a new account, return JWT
  POST /api/auth/login     — verify credentials, return JWT
  GET  /api/auth/me        — return the currently authenticated user

All password handling and JWT logic is delegated to app/services/auth_service.py.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserRegister, UserLogin, UserOut, TokenResponse
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter()


# ── Register ──────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user.

    1. Check the email is not already taken.
    2. Hash the password with bcrypt.
    3. Persist the new user to the database.
    4. Return a JWT access token so the user is immediately logged in.
    """
    # 1. Duplicate email check
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # 2 & 3. Hash password and persist
    new_user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)   # populates auto-generated fields (id, created_at)

    # 4. Issue token
    token = create_access_token(subject=new_user.id)
    return TokenResponse(
        access_token=token,
        user=UserOut.model_validate(new_user),
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive a JWT",
)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate an existing user.

    1. Look up the user by email.
    2. Verify the supplied password against the stored bcrypt hash.
    3. Return a JWT access token.

    A deliberately vague error message is used on failure so attackers
    cannot determine whether the email exists in the system.
    """
    # Use the same error for both "email not found" and "wrong password"
    # to prevent user-enumeration attacks.
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise auth_error

    if not verify_password(payload.password, user.hashed_password):
        raise auth_error

    token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


# ── Me (protected route example) ─────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserOut,
    summary="Get the currently authenticated user",
)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the profile of the user identified by the bearer token.
    This also serves as a live test that JWT validation works end-to-end.
    """
    return UserOut.model_validate(current_user)
