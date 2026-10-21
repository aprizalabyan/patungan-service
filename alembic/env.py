from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.db.base import Base
from app import models  # noqa: F401  (registers all tables on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# compare_type detects column type changes; enums are handled by SQLAlchemy's
# PostgreSQL dialect (CREATE TYPE on table create). Note: Alembic does not
# autogenerate changes to enum *members* or drop enum types -- edit those by hand.
_context_opts = dict(target_metadata=target_metadata, compare_type=True)


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_context_opts,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Tests may hand in an open connection via config.attributes["connection"].
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, **_context_opts)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, **_context_opts)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
