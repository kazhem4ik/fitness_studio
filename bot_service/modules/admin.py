import httpx
import logging
from sqlalchemy import select
from bot_service.core.database import AsyncSessionLocal
from bot_service.models.settings import StudioSettings

logger = logging.getLogger(__name__)

admin_states = {}

async def send_admin_panel(chat_id: int, bot_token: str):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(StudioSettings).where(StudioSettings.id == 1))
            studio_settings = result.scalar_one_or_none()
            
            if not studio_settings:
                logger.error("StudioSettings not found in database!")
                return
                
            text = (
                "⚙️ *Настройки студии*\n\n"
                f"Открытие: {studio_settings.open_time}\n"
                f"Закрытие: {studio_settings.close_time}\n"
                f"Длительность слота (мин): {studio_settings.slot_duration}\n"
                f"Начало обеда: {studio_settings.lunch_start}\n"
                f"Конец обеда: {studio_settings.lunch_end}\n"
                f"Рабочие дни (0-Пн, 6-Вс): {studio_settings.work_days}\n\n"
                "Выберите параметр для редактирования:"
            )
            
            keyboard = {
                "inline_keyboard": [
                    [{"text": "✏️ Открытие", "callback_data": "edit_open_time"}, {"text": "✏️ Закрытие", "callback_data": "edit_close_time"}],
                    [{"text": "✏️ Длит. слота", "callback_data": "edit_slot_duration"}],
                    [{"text": "✏️ Начало обеда", "callback_data": "edit_lunch_start"}, {"text": "✏️ Конец обеда", "callback_data": "edit_lunch_end"}],
                    [{"text": "✏️ Рабочие дни", "callback_data": "edit_work_days"}],
                ]
            }
            
        async with httpx.AsyncClient() as client:
            await client.post(
                url_send_message,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "reply_markup": keyboard
                }
            )
    except Exception as e:
        logger.error(f"Error sending admin panel: {e}")

async def handle_admin_callback(chat_id: int, data: str, bot_token: str):
    field_to_edit = data.replace("edit_", "")
    admin_states[chat_id] = field_to_edit
    
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(
            url_send_message,
            json={
                "chat_id": chat_id,
                "text": f"Отправьте новое значение для параметра `{field_to_edit}`:",
                "parse_mode": "Markdown"
            }
        )

async def handle_admin_text(chat_id: int, text: str, bot_token: str):
    if chat_id not in admin_states:
        return False  # Not waiting for input
        
    field_to_edit = admin_states[chat_id]
    
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(StudioSettings).where(StudioSettings.id == 1))
            studio_settings = result.scalar_one_or_none()
            
            if studio_settings:
                if field_to_edit == "slot_duration":
                    setattr(studio_settings, field_to_edit, int(text))
                else:
                    setattr(studio_settings, field_to_edit, text)
                await session.commit()
                
        del admin_states[chat_id]
        
        url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(
                url_send_message,
                json={
                    "chat_id": chat_id,
                    "text": "✅ Настройки успешно обновлены!"
                }
            )
            
        await send_admin_panel(chat_id, bot_token)
        return True
    except ValueError:
        url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        async with httpx.AsyncClient() as client:
            await client.post(
                url_send_message,
                json={
                    "chat_id": chat_id,
                    "text": "❌ Ошибка: Неверный формат данных. Попробуйте еще раз."
                }
            )
        return True
    except Exception as e:
        logger.error(f"Error updating admin settings: {e}")
        return True
