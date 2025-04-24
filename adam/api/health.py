from fastapi import APIRouter

health_router = APIRouter()


@health_router.get("/health", tags=["System"])
async def healthcheck():
    status = {"status": "ok"}
    return status
