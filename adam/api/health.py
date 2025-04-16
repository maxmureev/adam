from fastapi import APIRouter

health_router = APIRouter(tags=["Health"])


@health_router.get("/health")
async def healthcheck():
    status = {"status": "ok"}
    return status
