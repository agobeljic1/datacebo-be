from fastapi import FastAPI

from app.core.settings import settings
from app.routers.auth import router as auth_router
from app.routers.balance import router as balance_router
from app.routers.packages import router as packages_router
from app.routers.store import router as store_router
from app.routers.licenses import router as licenses_router
from app.routers.me import router as me_router
from app.routers.users import router as users_router
from app.startup import register_startup

app = FastAPI(title=settings.app_name)

register_startup(app)

app.include_router(auth_router, prefix="/auth", tags=["auth"]) 
app.include_router(balance_router, prefix="/balance", tags=["balance"]) 
app.include_router(packages_router, prefix="/packages", tags=["packages"]) 
app.include_router(store_router, prefix="/store", tags=["store"]) 
app.include_router(licenses_router, prefix="/licenses", tags=["licenses"]) 
app.include_router(me_router, tags=["me"]) 
app.include_router(users_router, tags=["users"]) 


@app.get("/health")
def health_check():
    return {"status": "ok"}
