import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

import api
import web
from models.database import init_db
from config import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

# Добавляем middleware для сессий
app.add_middleware(
    SessionMiddleware, secret_key=config.encryption.secret_key.get_secret_value()
)

app.include_router(api.api_router)
app.include_router(web.home_router)
app.include_router(api.health_router)
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.run.host,
        port=config.run.port,
        reload=True,
        log_config=None,
        log_level="info",
    )
