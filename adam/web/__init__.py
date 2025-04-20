from fastapi import APIRouter
from .home import home_router
from .health import health_router

router = APIRouter()
router.include_router(home_router)
router.include_router(health_router)
