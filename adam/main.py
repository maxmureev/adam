import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
from services.restrict_access import restrict_access_middleware

import api
import web
from models.database import init_db
from config import config
from services.logging_config import setup_logging, log_requests_middleware, get_logger


setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application")
    init_db()
    yield
    logger.info("Shutting down application")


app = FastAPI(lifespan=lifespan)

# Middleware for logging HTTP requests
app.middleware("http")(log_requests_middleware)

# Middleware for sessions
app.add_middleware(
    SessionMiddleware, secret_key=config.encryption.secret_key.get_secret_value()
)

# Middleware restrict access
app.middleware("http")(restrict_access_middleware)

app.include_router(api.api_router)
app.include_router(api.health_router)
app.include_router(web.home_router)
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.run.host,
        port=config.run.port,
        reload=True,
        log_config=None,
        log_level="error",
    )
