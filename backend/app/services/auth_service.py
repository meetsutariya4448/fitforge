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
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken

log = logging.getLogger(__name__)

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

# A refresh token is single-use: redeeming it revokes it and mints a replacement.
# Two things make that safe under concurrency:
#
#   1. The revoke is an atomic conditional UPDATE (revoked_at IS NULL in the
#      WHERE clause), so when N requests redeem the same token simultaneously
#      the database — not application logic — picks exactly one winner.  A
#      read-then-write would let every racer pass the "is it revoked?" check
#      before any of them wrote, minting N independent replacement branches.
#
#   2. Losing a race is not the same as replaying a stolen token.  A browser
#      with two tabs open can legitimately submit the same token twice within
#      milliseconds.  So a replay is only treated as theft once the benign
#      window has passed; inside it the caller is simply told to re-read the
#      token its sibling request already stored.

# How long after a successful rotation a replay of the parent token is treated
# as a benign concurrent double-submit rather than as token theft.
REFRESH_RACE_GRACE_SECONDS = 10


class RefreshError(HTTPException):
    """401 for a refresh-token failure, carrying a machine-readable reason.

    The reason surfaces as `error.code` in the response body (REFRESH_RACE,
    REFRESH_REUSE, REFRESH_INVALID, REFRESH_EXPIRED) via the app-wide handler
    in main.py.  The distinction that matters to the frontend is REFRESH_RACE —
    the session is fine, a sibling request rotated first and the caller should
    re-read its stored token — versus everything else, where the session is
    over and storage should be cleared.
    """

    def __init__(self, code: str, message: str):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
            headers={"WWW-Authenticate": "Bearer"},
        )
        self.code = code
        self.error_code = f"REFRESH_{code.upper()}"


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _new_token_row(
    user_id: int,
    *,
    family_id: str,
    device_info: Optional[str] = None,
) -> tuple[str, RefreshToken]:
    """Build (raw_token, unpersisted RefreshToken row). Caller owns the commit."""
    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    return raw, RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        family_id=family_id,
        device_info=device_info,
        expires_at=expires_at,
    )


def create_refresh_token(user_id: int, db: Session, device_info: Optional[str] = None) -> str:
    """
    Mint a new refresh token at the root of a fresh family (login / register),
    persist its SHA-256 hash, and return the raw value.

    The raw token is returned exactly once and never stored — only the hash
    is kept in the DB. The caller must include it in the HTTP response immediately.
    """
    raw, row = _new_token_row(user_id, family_id=str(uuid.uuid4()), device_info=device_info)
    db.add(row)
    db.commit()
    return raw


def _reject_unclaimable(token_hash: str, db: Session) -> None:
    """Diagnose why an atomic claim matched no row, and always raise.

    Called only after the conditional UPDATE failed, so the token is unknown,
    expired, or already redeemed.  The already-redeemed case is where reuse
    detection lives.
    """
    # `within_grace` is evaluated by the database rather than in Python: it is a
    # comparison against revoked_at, which the database itself wrote, so keeping
    # both on the same clock removes app/DB clock skew from the decision.
    row = db.execute(
        text(
            """
            SELECT user_id,
                   family_id,
                   revoked_at IS NOT NULL AS is_revoked,
                   replaced_by IS NOT NULL AS was_redeemed,
                   (clock_timestamp() - revoked_at)
                       <= make_interval(secs => :grace_seconds) AS within_grace
              FROM refresh_tokens
             WHERE token_hash = :token_hash
            """
        ),
        {"token_hash": token_hash, "grace_seconds": REFRESH_RACE_GRACE_SECONDS},
    ).one_or_none()

    if row is None:
        raise RefreshError("invalid", "Refresh token invalid or expired.")

    if not row.is_revoked:
        # Present and unrevoked, yet the claim still failed → it lapsed.
        raise RefreshError("expired", "Refresh token invalid or expired.")

    if row.was_redeemed and row.within_grace:
        # A sibling request won the race moments ago.  The session is healthy —
        # the replacement token exists, this caller just isn't the one holding
        # it.  Revoking the family here would log out a user for opening a
        # second tab, so leave it be.
        raise RefreshError(
            "race",
            "This refresh token was just rotated by a concurrent request.",
        )

    # Either a replay long after redemption, or a token revoked by logout being
    # presented again.  Both mean someone holds a copy they should not be able
    # to use, and we cannot tell which holder is the legitimate one — so cut off
    # the entire family and force a fresh login.
    revoked_count = db.execute(
        text(
            "UPDATE refresh_tokens SET revoked_at = clock_timestamp() "
            "WHERE family_id = :family_id AND revoked_at IS NULL"
        ),
        {"family_id": row.family_id},
    ).rowcount
    db.commit()

    log.warning(
        "Refresh token reuse detected for user_id=%s family=%s — revoked %d live token(s).",
        row.user_id,
        row.family_id,
        revoked_count,
    )
    raise RefreshError("reuse", "Refresh token invalid or expired.")


def rotate_refresh_token(raw_token: str, db: Session) -> tuple[str, int]:
    """
    Atomically redeem the provided refresh token and issue a replacement.

    Returns (new_raw_refresh_token, user_id).
    Raises RefreshError (401) if the token is unknown, expired, already
    redeemed, or lost a concurrent redemption race.

    The revoke and the mint share one transaction, so a crash between them
    cannot leave the caller with a revoked token and no replacement.
    """
    token_hash = _hash_token(raw_token)

    # The atomic claim.  `revoked_at IS NULL` in the WHERE clause is what makes
    # this safe: concurrent callers serialise on the row lock, and everyone who
    # arrives after the winner commits matches zero rows.
    #
    # Written as explicit SQL rather than an ORM-enabled update().returning():
    # the ORM form rewrites the RETURNING clause for session synchronisation and
    # was observed mis-mapping adjacent columns of the same type (family_id and
    # device_info arrived swapped) when several sessions executed it
    # concurrently.  This statement is the security boundary of the whole
    # rotation scheme, so it says exactly what it means.
    claimed = db.execute(
        text(
            """
            UPDATE refresh_tokens
               SET revoked_at = clock_timestamp()
             WHERE token_hash = :token_hash
               AND revoked_at IS NULL
               AND expires_at > clock_timestamp()
            RETURNING id, user_id, family_id, device_info
            """
        ),
        {"token_hash": token_hash},
    ).one_or_none()

    if claimed is None:
        db.rollback()
        _reject_unclaimable(token_hash, db)  # always raises

    new_raw, new_row = _new_token_row(
        claimed.user_id,
        family_id=claimed.family_id,
        device_info=claimed.device_info,
    )
    db.add(new_row)
    db.flush()  # assign new_row.id without ending the transaction

    # Marks the parent as legitimately redeemed — this is what distinguishes a
    # concurrent double-submit from a replay in _reject_unclaimable.
    db.execute(
        text("UPDATE refresh_tokens SET replaced_by = :child WHERE id = :parent"),
        {"child": new_row.id, "parent": claimed.id},
    )
    db.commit()

    return new_raw, claimed.user_id


def revoke_refresh_token(raw_token: str, db: Session) -> None:
    """Mark a refresh token revoked (used on logout). Silent no-op if not found."""
    db.execute(
        text(
            "UPDATE refresh_tokens SET revoked_at = clock_timestamp() "
            "WHERE token_hash = :token_hash AND revoked_at IS NULL"
        ),
        {"token_hash": _hash_token(raw_token)},
    )
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
