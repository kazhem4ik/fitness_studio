import httpx
import logging
from sqlalchemy import select
from bot_service.core.database import AsyncSessionLocal
from bot_service.models.settings import StudioSettings
from bot_service.models.days_off import DayOff
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

admin_states = {}

PROMPTS = {
    "open_time": "Введите время открытия студии в формате ЧЧ:ММ (например, 10:00):",
    "close_time": "Введите время закрытия студии в формате ЧЧ:ММ (например, 20:00):",
    "slot_duration": "Введите длительность одной тренировки в минутах (например, 75):",
    "lunch_start": "Введите время начала обеденного перерыва в формате ЧЧ:ММ (например, 14:00):",
    "lunch_end": "Введите время окончания обеденного перерыва в формате ЧЧ:ММ (например, 15:00):"
}

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
                f"Конец обеда: {studio_settings.lunch_end}\n\n"
                "Выберите параметр для редактирования:"
            )
            
            keyboard = {
                "inline_keyboard": [
                    [{"text": "✏️ Открытие", "callback_data": "edit_open_time"}, {"text": "✏️ Закрытие", "callback_data": "edit_close_time"}],
                    [{"text": "✏️ Длит. слота", "callback_data": "edit_slot_duration"}],
                    [{"text": "✏️ Начало обеда", "callback_data": "edit_lunch_start"}, {"text": "✏️ Конец обеда", "callback_data": "edit_lunch_end"}],
                    [{"text": "🗓 Календарь выходных", "callback_data": "admin_cal_0"}],
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

async def send_admin_calendar(chat_id: int, week_offset: int, bot_token: str, message_id: int = None):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    url_edit_message = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    
    dates_in_week = [start_of_week + timedelta(days=i) for i in range(7)]
    
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DayOff).where(DayOff.date >= dates_in_week[0], DayOff.date <= dates_in_week[-1])
            )
            days_off = {do.date for do in result.scalars()}
            
        inline_keyboard = []
        for d in dates_in_week:
            is_off = d in days_off
            marker = "🔴" if is_off else "🟢"
            btn_text = f"{marker} {d.strftime('%d.%m')} ({d.strftime('%a')})"
            cb_data = f"toggle_off_{week_offset}_{d.strftime('%Y-%m-%d')}"
            inline_keyboard.append([{"text": btn_text, "callback_data": cb_data}])
            
        nav_row = []
        if week_offset > 0:
            nav_row.append({"text": "⬅️ Назад", "callback_data": f"admin_cal_{week_offset-1}"})
        nav_row.append({"text": "Вперед ➡️", "callback_data": f"admin_cal_{week_offset+1}"})
        
        inline_keyboard.append(nav_row)
        inline_keyboard.append([{"text": "🔙 В настройки", "callback_data": "admin_panel"}])
        
        keyboard = {"inline_keyboard": inline_keyboard}
        text = f"🗓 *Календарь выходных*\n\nНеделя: {dates_in_week[0].strftime('%d.%m')} - {dates_in_week[-1].strftime('%d.%m')}\nНажмите на дату, чтобы сделать её выходным (🔴) или рабочим (🟢) днем."
        
        async with httpx.AsyncClient() as client:
            if message_id:
                await client.post(
                    url_edit_message,
                    json={
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": text,
                        "parse_mode": "Markdown",
                        "reply_markup": keyboard
                    }
                )
            else:
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
        logger.error(f"Error sending admin calendar: {e}")

async def handle_admin_callback(chat_id: int, data: str, bot_token: str):
    field_to_edit = data.replace("edit_", "")
    admin_states[chat_id] = field_to_edit
    
    prompt_text = PROMPTS.get(field_to_edit, f"Отправьте новое значение для параметра `{field_to_edit}`:")
    
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(
            url_send_message,
            json={
                "chat_id": chat_id,
                "text": prompt_text,
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
