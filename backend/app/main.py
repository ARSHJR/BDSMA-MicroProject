from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import catalog, user, analytics
from .store import get_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_store()  # warm models at startup
    yield


app = FastAPI(title="Fashion Recommender API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_methods=["*"], allow_headers=["*"])
for r in (catalog.router, user.router, analytics.router):
    app.include_router(r)
