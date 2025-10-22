from fastapi import FastAPI

from app.core.settings import settings
from app.routers.auth import router as auth_router
from app.startup import register_startup

app = FastAPI(title=settings.app_name)

register_startup(app)

app.include_router(auth_router, prefix="/auth", tags=["auth"]) 


@app.get("/health")
def health_check():
    return {"status": "ok"}
