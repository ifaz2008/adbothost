from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_compatible_schema()


def ensure_compatible_schema() -> None:
    """Small MVP schema guard for nullable columns added before Alembic exists."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    additions_by_table = {
        "credit_transactions": {
            "reference_type": "VARCHAR(80)",
            "visible_reason": "VARCHAR(255)",
            "internal_reason": "TEXT",
            "admin_id": "INTEGER",
        },
        "plans": {
            "credit_multiplier": "FLOAT DEFAULT 1 NOT NULL",
        },
        "bots": {
            "active_until": "TIMESTAMP",
        },
    }
    with engine.begin() as connection:
        for table_name, additions in additions_by_table.items():
            if table_name not in tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for name, column_type in additions.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {column_type}"))
