"""
Authentication router.

Endpoints:
  POST /api/auth/register  — create a new account, return JWT + refresh token
  POST /api/auth/login     — verify credentials, return JWT + refresh token
  POST /api/auth/refresh   — rotate refresh token, return new JWT + refresh token
  POST /api/auth/logout    — revoke the refresh token (silent if token unknown)
  GET  /api/auth/me        — return the currently authenticated user

All password handling, JWT logic, and refresh-token management are delegated
to app/services/auth_service.py.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.schemas.user import UserRegister, UserLogin, UserOut, TokenResponse, RefreshRequest, DeleteAccountRequest
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
    get_current_user,
)

import logging
log = logging.getLogger(__name__)

router = APIRouter()


def _device_info(request: Request) -> str:
    return request.headers.get("User-Agent", "unknown")[:255]


# ── Register ──────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
)
@limiter.limit("10/minute")
def register(payload: UserRegister, request: Request, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    new_user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token(subject=new_user.id)
    refresh_token = create_refresh_token(new_user.id, db, device_info=_device_info(request))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(new_user),
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive a JWT + refresh token",
)
@limiter.limit("10/minute")
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
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

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(user.id, db, device_info=_device_info(request))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


# ── Refresh ───────────────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and receive a new JWT pair",
)
@limiter.limit("20/minute")
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    new_refresh, user_id = rotate_refresh_token(payload.refresh_token, db)

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    access_token = create_access_token(subject=user_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        user=UserOut.model_validate(user),
    )


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the refresh token",
)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    revoke_refresh_token(payload.refresh_token, db)


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserOut,
    summary="Get the currently authenticated user",
)
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


# ── Delete account ─────────────────────────────────────────────────────────────

@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete account and all associated data",
)
def delete_account(
    payload: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Hard-delete the authenticated user and cascade-purge all user data:
    workout plans, sessions, exercise logs, personal records, and refresh tokens.

    Requires password confirmation. Returns 204 on success.
    All cascades are enforced at the DB level (ON DELETE CASCADE).
    """
    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Account not deleted.",
        )

    user_id = current_user.id
    db.delete(current_user)
    db.commit()
    log.info("Deleted account user_id=%d and all associated data.", user_id)
