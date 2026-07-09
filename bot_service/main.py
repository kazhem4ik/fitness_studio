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
    # Выполняется при старте сервера
    async with httpx.AsyncClient() as client:
        # Удаляем вебхук Telegram и запускаем long polling
        if settings.TG_BOT_TOKEN:
            tg_api_delete_url = f"https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/deleteWebhook"
            try:
                delete_resp = await client.post(tg_api_delete_url)
                logger.info(f"Telegram deleteWebhook response: {delete_resp.json()}")
                
                # Запускаем поллинг в фоновой задаче
                asyncio.create_task(start_tg_polling(settings.TG_BOT_TOKEN))
            except Exception as e:
                logger.error(f"Failed to delete Telegram webhook or start polling: {e}")

        # Установка вебхука MAX (временно закомментирована для локальной разработки)
        # if settings.MAX_BOT_TOKEN:
        #     webhook_url_max = f"{settings.WEBHOOK_HOST.rstrip('/')}/webhook/max"
        #     max_api_url = f"https://api.maxbot.com/v1/bot{settings.MAX_BOT_TOKEN}/setWebhook"
        #     try:
        #         max_resp = await client.post(max_api_url, json={"url": webhook_url_max})
        #         logger.info(f"MAX setWebhook response: {max_resp.text}")
        #     except Exception as e:
        #         logger.error(f"Failed to set MAX webhook: {e}")
            
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
