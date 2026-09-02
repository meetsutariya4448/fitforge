"""
Authentication service.

Provides three responsibilities:
  1. Password hashing / verification  (bcrypt via passlib)
  2. JWT creation / decoding           (HS256 via python-jose)
  3. get_current_user dependency       (FastAPI Depends-injectable)

Routes import these functions instead of touching jose/passlib directly,
keeping auth logic centralised and easy to unit-test.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken

# ── Password hashing ──────────────────────────────────────────────────────────

# bcrypt is the recommended scheme; deprecated="auto" will gracefully handle
# any future scheme migrations without breaking existing hashes.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    truncated = plain_password[:72]
    return _pwd_context.hash(truncated)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the stored bcrypt hash."""
    return _pwd_context.verify(plain_password, hashed_password)


# ── JWT ───────────────────────────────────────────────────────────────────────

# OAuth2PasswordBearer tells FastAPI where to find the token in requests
# (Authorization: Bearer <token>) and auto-populates the Swagger "Authorize" UI.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def create_access_token(subject: int) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: The user's integer ID — stored in the `sub` claim.

    Returns:
        A signed JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(subject),   # JWT spec: sub should be a string
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _decode_token(token: str) -> Optional[int]:
    """
    Decode and validate a JWT token.

    Returns the user ID (int) on success, or None if the token is
    invalid / expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return int(user_id)
    except JWTError:
        return None


# ── Refresh tokens ────────────────────────────────────────────────────────────

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_refresh_token(user_id: int, db: Session, device_info: Optional[str] = None) -> str:
    """
    Mint a new refresh token, persist its SHA-256 hash, and return the raw value.

    The raw token is returned exactly once and never stored — only the hash
    is kept in the DB. The caller must include it in the HTTP response immediately.
    """
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    row = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        device_info=device_info,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    return raw


def rotate_refresh_token(raw_token: str, db: Session) -> tuple[str, int]:
    """
    Validate the provided refresh token, revoke it, and issue a new pair.

    Returns (new_raw_refresh_token, user_id).
    Raises HTTP 401 if the token is unknown, already revoked, or expired.
    """
    token_hash = _hash_token(raw_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token invalid or expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if row is None:
        raise invalid
    if row.revoked_at is not None:
        raise invalid
    if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise invalid

    # Revoke the used token — strict rotation: each token is one-time use.
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()

    new_raw = create_refresh_token(row.user_id, db, device_info=row.device_info)
    return new_raw, row.user_id


def revoke_refresh_token(raw_token: str, db: Session) -> None:
    """Mark a refresh token revoked (used on logout). Silent no-op if not found."""
    token_hash = _hash_token(raw_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()


# ── FastAPI dependency ─────────────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that extracts and validates the bearer token,
    then returns the authenticated User ORM object.

    Usage in a protected route:
        def my_route(current_user: User = Depends(get_current_user)): ...

    Raises:
        HTTPException 401 — if the token is missing, invalid, or the user
                            no longer exists in the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = _decode_token(token)
    if user_id is None:
        raise credentials_exception

    user = db.get(User, user_id)
    if user is None:
        raise credentials_exception

    from app.tracing import update_trace
    update_trace(user_id=user_id)

    return user
