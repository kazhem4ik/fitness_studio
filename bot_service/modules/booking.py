import httpx
import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from bot_service.core.database import AsyncSessionLocal
from bot_service.models.users import User
from bot_service.models.bookings import Booking
from bot_service.core.config import settings

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

async def confirm_booking(chat_id: int, slot_data: str, bot_token: str):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.telegram_id == str(chat_id)))
            user = result.scalar_one_or_none()
            
            if not user:
                logger.error(f"User {chat_id} not found when confirming booking")
                return
            
            now = datetime.now()
            if slot_data == "slot_1":
                session_time = now.replace(hour=18, minute=0, second=0, microsecond=0) + timedelta(days=1)
            elif slot_data == "slot_2":
                session_time = now.replace(hour=19, minute=0, second=0, microsecond=0) + timedelta(days=1)
            else:
                logger.error(f"Unknown slot data: {slot_data}")
                return
                
            new_booking = Booking(
                user_id=user.id,
                session_start=session_time,
                is_trial=True,
                status="scheduled"
            )
            session.add(new_booking)
            await session.commit()
            logger.info(f"Booking confirmed for user {user.id} at {session_time}")
            
        async with httpx.AsyncClient() as client:
            await client.post(
                url_send_message,
                json={
                    "chat_id": chat_id,
                    "text": "✅ Отлично! Вы успешно записаны на пробную тренировку. Тренер свяжется с вами для подтверждения деталей."
                }
            )
            
            if settings.ADMIN_CHAT_ID:
                await client.post(
                    url_send_message,
                    json={
                        "chat_id": settings.ADMIN_CHAT_ID,
                        "text": f"🔔 Новая запись на пробную тренировку!\nКлиент: {user.full_name} (TG ID: {user.telegram_id})\nВремя: {session_time.strftime('%d.%m.%Y %H:%M')}"
                    }
                )
    except Exception as e:
        logger.error(f"Error during booking confirmation for {chat_id}: {e}")
