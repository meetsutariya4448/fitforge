"""
SQLAlchemy database setup.

Provides:
  - engine       : connects to PostgreSQL using DATABASE_URL from settings
  - SessionLocal : session factory (one session per request)
  - Base         : declarative base that all ORM models inherit from
  - get_db       : FastAPI dependency that yields a DB session and
                   guarantees it is closed after the request completes
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


# ── Engine ────────────────────────────────────────────────────────────────────
# pool_pre_ping=True checks the connection on checkout, recovering gracefully
# from database restarts without raising stale-connection errors.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ── Declarative base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this class."""
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────
def get_db():
    """
    Yield a database session for the duration of a single request.

    Usage in a route:
        def my_route(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
