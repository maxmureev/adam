from fastapi import APIRouter
from config import config
from .v1 import v1_router
from .auth import auth_router
from .health import health_router

# from .v2 import v2_router


api_router = APIRouter(prefix=config.api.prefix)
api_router.include_router(auth_router)
api_router.include_router(v1_router)
api_router.include_router(health_router)


# api_router.include_router(v2_router)
