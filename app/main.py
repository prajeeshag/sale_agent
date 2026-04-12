from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.services.search import init_searcher
from app.services.whatsapp import init_provider
from app.api.webhook import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_searcher(settings.index_path, settings.id_map_path)
    init_provider()
    yield


app = FastAPI(
    title="Sale Agent — WhatsApp Visual Search",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(webhook_router)
