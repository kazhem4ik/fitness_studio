import asyncio
import httpx
import logging

logger = logging.getLogger(__name__)

async def start_tg_polling(bot_token: str):
    url_get_updates = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    offset = None
    timeout = 20
    
    logger.info("Starting Telegram long polling...")
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                params = {"timeout": timeout}
                if offset:
                    params["offset"] = offset
                    
                response = await client.get(url_get_updates, params=params, timeout=timeout + 5)
                response.raise_for_status()
                data = response.json()
                
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        
                        message = update.get("message")
                        if message and "text" in message:
                            text = message["text"]
                            chat_id = message["chat"]["id"]
                            
                            if text == "/start":
                                await client.post(
                                    url_send_message,
                                    json={
                                        "chat_id": chat_id,
                                        "text": "Привет! Добро пожаловать в нашу фитнес-студию. Выберите время для пробной тренировки."
                                    }
                                )
                                logger.info(f"Sent /start response to {chat_id}")
            except httpx.RequestError as e:
                logger.error(f"Network error during polling: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error during polling: {e}")
                await asyncio.sleep(5)
