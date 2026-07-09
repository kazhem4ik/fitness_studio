import httpx
import logging
from datetime import datetime, timedelta, time
from sqlalchemy import select
from bot_service.core.database import AsyncSessionLocal
from bot_service.models.users import User
from bot_service.models.bookings import Booking
from bot_service.core.config import settings

logger = logging.getLogger(__name__)

async def handle_booking_request(chat_id: int, bot_token: str):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        async with AsyncSessionLocal() as session:
            tomorrow = datetime.now().date() + timedelta(days=1)
            start_of_day = datetime.combine(tomorrow, time.min)
            end_of_day = datetime.combine(tomorrow, time.max)
            
            result = await session.execute(
                select(Booking).where(Booking.session_start >= start_of_day, Booking.session_start <= end_of_day)
            )
            booked_times = {b.session_start.hour for b in result.scalars()}
            
            available_hours = [h for h in range(10, 21) if h not in booked_times]
            
            if not available_hours:
                text = "К сожалению, на завтра все окна заняты. Попробуйте проверить позже."
                keyboard = None
            else:
                text = "Доступные окна на завтра:"
                inline_keyboard = []
                row = []
                for h in available_hours:
                    row.append({"text": f"Завтра {h}:00", "callback_data": f"slot_{h}:00"})
                    if len(row) == 2:  # группируем по 2 кнопки
                        inline_keyboard.append(row)
                        row = []
                if row:
                    inline_keyboard.append(row)
                keyboard = {"inline_keyboard": inline_keyboard}

        async with httpx.AsyncClient() as client:
            payload = {
                "chat_id": chat_id,
                "text": text
            }
            if keyboard:
                payload["reply_markup"] = keyboard
                
            response = await client.post(url_send_message, json=payload)
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
            
            try:
                hour = int(slot_data.split("_")[1].split(":")[0])
            except (IndexError, ValueError):
                logger.error(f"Invalid slot data format: {slot_data}")
                return
                
            tomorrow = datetime.now().date() + timedelta(days=1)
            session_time = datetime.combine(tomorrow, time(hour=hour))
            
            existing_booking = await session.execute(
                select(Booking).where(Booking.session_start == session_time)
            )
            if existing_booking.scalar_one_or_none():
                async with httpx.AsyncClient() as client:
                    await client.post(
                        url_send_message,
                        json={
                            "chat_id": chat_id,
                            "text": "Упс! Это время только что заняли. Пожалуйста, выберите другое."
                        }
                    )
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
