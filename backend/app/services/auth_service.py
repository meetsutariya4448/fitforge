"""
Authentication service.

Provides three responsibilities:
  1. Password hashing / verification  (bcrypt via passlib)
  2. JWT creation / decoding           (HS256 via python-jose)
  3. get_current_user dependency       (FastAPI Depends-injectable)

Routes import these functions instead of touching jose/passlib directly,
keeping auth logic centralised and easy to unit-test.
"""

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

    return user
