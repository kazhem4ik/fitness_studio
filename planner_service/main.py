from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from planner_service.core.config import settings
from planner_service.core.database import init_db
from planner_service.api.auth import router as auth_router
from planner_service.api.appointments import router as appointments_router
from planner_service.api.clients import router as clients_router
from planner_service.api.finances import router as finances_router
from planner_service.api.public_booking import router as public_booking_router

# Абсолютный путь к директории static
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация БД при старте."""
    logger.info("🗄️ Initializing planner database...")
    await init_db()
    logger.info("✅ Planner service is ready!")
    yield
    logger.info("👋 Planner service shutting down...")


app = FastAPI(
    title="Fitness Planner",
    docs_url="/clients/api/docs",
    openapi_url="/clients/api/openapi.json",
    lifespan=lifespan,
)

# API routes — под /clients/api/
app.include_router(auth_router, prefix="/clients")
app.include_router(appointments_router, prefix="/clients")
app.include_router(clients_router, prefix="/clients")
app.include_router(finances_router, prefix="/clients")
app.include_router(public_booking_router, prefix="/api/public")

# Статические файлы PWA — под /clients/static/
app.mount("/clients/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# PWA routes — отдаём index.html для всех frontend-маршрутов
@app.get("/clients")
@app.get("/clients/")
@app.get("/clients/login")
@app.get("/clients/day")
@app.get("/clients/week")
@app.get("/clients/month")
@app.get("/clients/clients")
@app.get("/clients/finances")
async def serve_spa():
    """SPA — всегда отдаём index.html, роутинг на клиенте."""
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/book")
async def serve_public_booking():
    """Публичная страница для самозаписи."""
    return FileResponse(STATIC_DIR / "book.html")



# PWA Manifest & Service Worker (должны быть в корне scope)
@app.get("/clients/manifest.json")
async def serve_manifest():
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/clients/sw.js")
async def serve_sw():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")
