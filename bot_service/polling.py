import asyncio
import httpx
import logging

from sqlalchemy import select
from bot_service.core.database import AsyncSessionLocal
from bot_service.models.users import User
from bot_service.models.bookings import Booking
from bot_service.models.progress import Progress
from bot_service.modules.booking import handle_booking_request, handle_booking_slots, confirm_booking
from bot_service.modules.nutrition import handle_nutrition_request, request_nutrition_consultation
from bot_service.modules.admin import handle_admin_text, send_admin_panel, handle_admin_callback
from bot_service.core.config import settings

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
                                try:
                                    async with AsyncSessionLocal() as session:
                                        result = await session.execute(select(User).where(User.telegram_id == str(chat_id)))
                                        user = result.scalar_one_or_none()
                                        
                                        if not user:
                                            first_name = message.get("from", {}).get("first_name", "Клиент")
                                            new_user = User(telegram_id=str(chat_id), full_name=first_name)
                                            session.add(new_user)
                                            await session.commit()
                                            logger.info(f"Registered new user: {chat_id} ({first_name})")
                                except Exception as db_err:
                                    logger.error(f"Database error during user registration: {db_err}")

                                inline_keyboard = [
                                    [{"text": "📅 Записаться на тренировку", "callback_data": "book_session"}],
                                    [{"text": "🍏 Мое питание", "callback_data": "nutrition"}]
                                ]
                                
                                if str(chat_id) == settings.ADMIN_CHAT_ID:
                                    inline_keyboard.append([{"text": "⚙️ Настройки студии", "callback_data": "admin_panel"}])
                                    
                                keyboard = {"inline_keyboard": inline_keyboard}
                                
                                await client.post(
                                    url_send_message,
                                    json={
                                        "chat_id": chat_id,
                                        "text": "Привет! Добро пожаловать в нашу фитнес-студию. Выберите нужный раздел.",
                                        "reply_markup": keyboard
                                    }
                                )
                                logger.info(f"Sent /start response to {chat_id}")
                            else:
                                await handle_admin_text(chat_id, text, bot_token)
                        elif "callback_query" in update:
                            callback_query = update["callback_query"]
                            cq_id = callback_query["id"]
                            data = callback_query["data"]
                            chat_id = callback_query["message"]["chat"]["id"]
                            
                            url_answer_callback = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
                            await client.post(
                                url_answer_callback,
                                json={"callback_query_id": cq_id}
                            )
                            
                            if data == "book_session":
                                await handle_booking_request(chat_id, bot_token)
                            elif data == "day_off":
                                url_answer_callback = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
                                await client.post(
                                    url_answer_callback,
                                    json={"callback_query_id": cq_id, "text": "В этот день студия не работает.", "show_alert": True}
                                )
                            elif data.startswith("date_"):
                                date_str = data.split("_")[1]
                                await handle_booking_slots(chat_id, date_str, bot_token)
                            elif data.startswith("slot_"):
                                await confirm_booking(chat_id, data, bot_token)
                            elif data == "nutrition":
                                await handle_nutrition_request(chat_id, bot_token)
                            elif data == "request_nutrition":
                                await request_nutrition_consultation(chat_id, bot_token)
                            elif data == "admin_panel":
                                await send_admin_panel(chat_id, bot_token)
                            elif data.startswith("edit_"):
                                await handle_admin_callback(chat_id, data, bot_token)
                            elif data.startswith("admin_cal_"):
                                week_offset = int(data.split("_")[2])
                                message_id = callback_query["message"]["message_id"]
                                from bot_service.modules.admin import send_admin_calendar
                                await send_admin_calendar(chat_id, week_offset, bot_token, message_id)
                            elif data.startswith("toggle_off_"):
                                parts = data.split("_")
                                week_offset = int(parts[2])
                                date_str = parts[3]
                                from datetime import datetime
                                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                                
                                async with AsyncSessionLocal() as session:
                                    from bot_service.models.days_off import DayOff
                                    result = await session.execute(select(DayOff).where(DayOff.date == target_date))
                                    day_off = result.scalar_one_or_none()
                                    if day_off:
                                        await session.delete(day_off)
                                    else:
                                        session.add(DayOff(date=target_date))
                                    await session.commit()
                                
                                message_id = callback_query["message"]["message_id"]
                                from bot_service.modules.admin import send_admin_calendar
                                await send_admin_calendar(chat_id, week_offset, bot_token, message_id)
            except httpx.RequestError as e:
                logger.error(f"Network error during polling: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error during polling: {e}")
                await asyncio.sleep(5)
