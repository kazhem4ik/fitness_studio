from contextlib import asynccontextmanager
import logging
import httpx
import asyncio
from fastapi import FastAPI

from bot_service.core.config import settings
from bot_service.api.tg_webhook import router as tg_router
from bot_service.api.max_webhook import router as max_router
from bot_service.polling import start_tg_polling

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.TG_BOT_TOKEN:
        tg_api_delete_url = f"https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/deleteWebhook"
        async with httpx.AsyncClient(
            proxy=settings.TG_PROXY_URL or None,
            timeout=httpx.Timeout(20.0, connect=10.0),
        ) as client:
            try:
                logger.info("Attempting to delete webhook...")
                delete_resp = await client.post(tg_api_delete_url)
                logger.info(f"Telegram deleteWebhook response: {delete_resp.text}")
            except httpx.RequestError as e:
                logger.warning(
                    "Telegram webhook cleanup is unavailable (%s: %r); polling will retry in background",
                    type(e).__name__,
                    e,
                )
        
        # Запускаем поллинг В ЛЮБОМ СЛУЧАЕ
        logger.info("Starting polling task...")
        asyncio.create_task(start_tg_polling(settings.TG_BOT_TOKEN))
            
    yield
    logger.info("Shutting down Fitness Studio Bot Service...")

app = FastAPI(title="Fitness Studio Bot Service", lifespan=lifespan)
app.include_router(tg_router)
app.include_router(max_router)

@app.get("/")
async def root():
    return {"message": "Fitness Studio Bot API is running."}
