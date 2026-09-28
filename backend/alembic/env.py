import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ─────────────────────────────────────────────────────────────────────
# Rendre le package "app" importable depuis env.py.
# env.py se trouve dans backend/alembic/ ; on ajoute backend/ au sys.path.
# ─────────────────────────────────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# app.config charge le fichier .env (python-dotenv) et expose DATABASE_URL.
# On lit donc l'URL depuis l'environnement, jamais en dur dans alembic.ini.
from app.config import DATABASE_URL  # noqa: E402
from app.database import Base  # noqa: E402

# IMPORTANT : importer les modèles pour que toutes les tables soient
# enregistrées sur Base.metadata (indispensable pour --autogenerate).
# Article, User et ActionLog sont tous définis dans app.models.
import app.models  # noqa: E402,F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Injecte l'URL de connexion issue de l'environnement (surcharge alembic.ini).
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Métadonnées cibles pour l'autogénération des migrations.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
