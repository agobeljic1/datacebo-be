from fastapi import FastAPI
from sqlalchemy import text, inspect

from app.db.session import Base, engine


def register_startup(app: FastAPI) -> None:
    @app.on_event("startup")
    def _create_tables() -> None:
        Base.metadata.create_all(bind=engine)

        # Lightweight migration: add missing columns that we depend on
        with engine.begin() as conn:
            inspector = inspect(conn)
            if "packages" in inspector.get_table_names():
                package_columns = {col["name"] for col in inspector.get_columns("packages")}
                if "is_deprecated" not in package_columns:
                    # SQLite/Postgres compatible boolean default
                    conn.execute(text("ALTER TABLE packages ADD COLUMN is_deprecated BOOLEAN NOT NULL DEFAULT 0"))
