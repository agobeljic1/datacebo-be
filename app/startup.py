from fastapi import FastAPI

from app.db.session import Base, engine


def register_startup(app: FastAPI) -> None:
    @app.on_event("startup")
    def _create_tables() -> None:
        Base.metadata.create_all(bind=engine)
