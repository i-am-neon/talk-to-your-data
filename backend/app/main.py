from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import settings
from app.routes.query import router as query_router
from app.routes.conversations import router as conversations_router

logfire.configure(
    token=settings.logfire_token or None,
)
logfire.instrument_pydantic_ai()
logfire.instrument_asyncpg()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.database_url:
        await db.init_pool(settings.database_url)
    yield
    await db.close_pool()


app = FastAPI(title="Data Agent API", lifespan=lifespan)
logfire.instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router)
app.include_router(conversations_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
