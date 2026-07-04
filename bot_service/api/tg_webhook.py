import logging
from fastapi import APIRouter, Request
import httpx
from bot_service.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/webhook/tg")
async def tg_webhook(request: Request):
    update = await request.json()
    logger.info(f"Incoming Telegram update: {update}")
    
    message = update.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    
    if text == "/start" and chat_id:
        url = f"https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "Привет! Добро пожаловать в нашу фитнес-студию. Выберите время для пробной тренировки."
        }
        async with httpx.AsyncClient() as client:
            try:
                await client.post(url, json=payload)
            except Exception as e:
                logger.error(f"Failed to send message to Telegram: {e}")
                
    return {"status": "ok"}
