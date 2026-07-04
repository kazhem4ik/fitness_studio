import logging
from fastapi import APIRouter, Request
import httpx
from bot_service.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/webhook/max")
async def max_webhook(request: Request):
    update = await request.json()
    logger.info(f"Incoming MAX update: {update}")
    
    # Примерная структура для платформы MAX API
    message = update.get("message", {})
    text = message.get("text", "")
    user_id = update.get("user_id") or message.get("from", {}).get("id")
    
    if text in ["/start", "start"] and user_id:
        url = f"https://api.maxbot.com/v1/bot{settings.MAX_BOT_TOKEN}/sendMessage"
        payload = {
            "user_id": user_id,
            "text": "Привет! Добро пожаловать в нашу фитнес-студию. Выберите время для пробной тренировки."
        }
        async with httpx.AsyncClient() as client:
            try:
                await client.post(url, json=payload)
            except Exception as e:
                logger.error(f"Failed to send message to MAX API: {e}")

    return {"status": "ok"}
