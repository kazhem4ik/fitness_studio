from contextlib import asynccontextmanager
import logging
import httpx
from fastapi import FastAPI

from bot_service.core.config import settings
from bot_service.api.tg_webhook import router as tg_router
from bot_service.api.max_webhook import router as max_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Выполняется при старте сервера
    webhook_url_tg = f"{settings.WEBHOOK_HOST.rstrip('/')}/webhook/tg"
    webhook_url_max = f"{settings.WEBHOOK_HOST.rstrip('/')}/webhook/max"
    
    async with httpx.AsyncClient() as client:
        # Установка вебхука Telegram
        if settings.TG_BOT_TOKEN:
            tg_api_url = f"https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/setWebhook"
            try:
                tg_resp = await client.post(tg_api_url, json={"url": webhook_url_tg})
                logger.info(f"Telegram setWebhook response: {tg_resp.json()}")
            except Exception as e:
                logger.error(f"Failed to set Telegram webhook: {e}")

        # Установка вебхука MAX
        if settings.MAX_BOT_TOKEN:
            max_api_url = f"https://api.maxbot.com/v1/bot{settings.MAX_BOT_TOKEN}/setWebhook"
            try:
                max_resp = await client.post(max_api_url, json={"url": webhook_url_max})
                logger.info(f"MAX setWebhook response: {max_resp.text}")
            except Exception as e:
                logger.error(f"Failed to set MAX webhook: {e}")
            
    yield
    # Выполняется при остановке сервера (опционально)
    logger.info("Shutting down Fitness Studio Bot Service...")

app = FastAPI(title="Fitness Studio Bot Service", lifespan=lifespan)

# Подключаем роутеры
app.include_router(tg_router)
app.include_router(max_router)

@app.get("/")
async def root():
    return {"message": "Fitness Studio Bot API is running. Webhooks configured."}
