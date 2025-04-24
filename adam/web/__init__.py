from fastapi import APIRouter
from .home import home_router

router = APIRouter()
router.include_router(home_router)
