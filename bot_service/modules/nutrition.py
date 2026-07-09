import httpx
import logging
from sqlalchemy import select
from bot_service.core.database import AsyncSessionLocal
from bot_service.models.users import User

logger = logging.getLogger(__name__)

async def handle_nutrition_request(chat_id: int, bot_token: str):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.telegram_id == str(chat_id)))
            user = result.scalar_one_or_none()
            
            if not user:
                logger.error(f"User {chat_id} not found when requesting nutrition")
                return
                
            if not user.nutrition_plan_active:
                text = "🍏 Правильное питание — это 70% успеха!\n\nУ вас пока не подключен индивидуальный план. Мы можем составить для вас семейный рацион, который легко готовить и вкусно есть."
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📝 Оставить заявку на разбор", "callback_data": "request_nutrition"}]
                    ]
                }
            else:
                text = "🍏 Панель питания\n\nНе забывайте присылать фото ваших приемов пищи!"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📸 Отправить дневник питания", "callback_data": "send_diary"}],
                        [{"text": "📋 Мой рацион", "callback_data": "my_ration"}]
                    ]
                }
                
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url_send_message,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "reply_markup": keyboard
                }
            )
            response.raise_for_status()
            logger.info(f"Sent nutrition menu to {chat_id}")
    except Exception as e:
        logger.error(f"Error during nutrition request for {chat_id}: {e}")
