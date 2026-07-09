import httpx
import logging

logger = logging.getLogger(__name__)

async def handle_booking_request(chat_id: int, bot_token: str):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Завтра 18:00", "callback_data": "slot_1"},
                {"text": "Завтра 19:00", "callback_data": "slot_2"}
            ]
        ]
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url_send_message,
                json={
                    "chat_id": chat_id,
                    "text": "Выберите доступное время для пробной тренировки:",
                    "reply_markup": keyboard
                }
            )
            response.raise_for_status()
            logger.info(f"Sent booking options to {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send booking options to {chat_id}: {e}")
