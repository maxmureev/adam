import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# from contextlib import asynccontextmanager

import api
import web
from models.database import init_db
from config import config

app = FastAPI()

app.include_router(api.api_router)
app.include_router(web.home_router)
app.include_router(api.health_router)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Инициализирует базу при старте
@app.on_event("startup")
async def startup():
    init_db()


# @asynccontextmanager
# async def lifespan():
#     init_db()


if __name__ == "__main__":
    uvicorn.run("main:app", host=config.run.host, port=config.run.port, reload=True)
