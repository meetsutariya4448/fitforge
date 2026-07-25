"""
Alembic environment configuration for FitForge.

Key changes from the default template:
  1. DATABASE_URL is read from app.config.settings (not alembic.ini) so
     a single .env file is the source of truth for the connection string.
  2. target_metadata is set to Base.metadata so `alembic revision --autogenerate`
     can diff the ORM models against the live database schema.
  3. All ORM models are imported via `app.models` so their tables are registered
     on Base.metadata before autogenerate runs.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── FitForge imports ──────────────────────────────────────────────────────────
from app.config import settings
from app.database import Base
import app.models  # noqa: F401 — registers User, WorkoutPlanRecord on Base.metadata

# ── Alembic config object ─────────────────────────────────────────────────────
config = context.config

# Wire the DATABASE_URL from settings into alembic's config at runtime.
# This means alembic.ini does NOT need a sqlalchemy.url line.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Tell Alembic which metadata to compare against for autogenerate
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    # kb_chunks uses TSVECTOR GENERATED ALWAYS AS ... STORED, which Alembic
    # autogenerate cannot model. Exclude this table so that future
    # `alembic revision --autogenerate` runs don't emit broken DDL for it.
    if type_ == "table" and name == "kb_chunks":
        return False
    return True


# ── Offline mode ──────────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations without a live DB connection.
    Useful for generating SQL scripts to review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode ───────────────────────────────────────────────────────────────

def run_migrations_online() -> None:
    """
    Run migrations against a live database connection.
    This is the mode used by `alembic upgrade head`.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
