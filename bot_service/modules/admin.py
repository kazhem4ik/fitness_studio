import httpx
import logging
from sqlalchemy import select
from bot_service.core.database import AsyncSessionLocal
from bot_service.models.settings import StudioSettings
from bot_service.models.daily_schedule import DailySchedule
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

admin_states = {}

PROMPTS = {
    "open_time": "Введите время открытия студии в формате ЧЧ:ММ (например, 10:00):",
    "close_time": "Введите время закрытия студии в формате ЧЧ:ММ (например, 20:00):",
    "slot_duration": "Введите длительность тренировки в минутах (например, 60):",
    "buffer_before": "Введите буфер ДО тренировки в минутах (например, 10):",
    "buffer_after": "Введите буфер ПОСЛЕ тренировки в минутах (например, 20):",
    "add_break": "Введите временной интервал перерыва в формате ЧЧ:ММ-ЧЧ:ММ (например, 16:00-16:30):"
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
                
            custom_breaks_str = studio_settings.custom_breaks if studio_settings.custom_breaks else "Нет"
            text = (
                "⚙️ *Настройки студии*\n\n"
                f"Открытие: {studio_settings.open_time}\n"
                f"Закрытие: {studio_settings.close_time}\n"
                f"Длительность тренировки (мин): {getattr(studio_settings, 'slot_duration', 60)}\n"
                f"Буфер до (мин): {getattr(studio_settings, 'buffer_before', 10)}\n"
                f"Буфер после (мин): {getattr(studio_settings, 'buffer_after', 20)}\n"
                f"Перерывы: {custom_breaks_str}\n\n"
                "Выберите параметр для редактирования:"
            )
            
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🌅 Открытие", "callback_data": "edit_open_time"}, {"text": "🌃 Закрытие", "callback_data": "edit_close_time"}],
                    [{"text": "⏱ Длительность", "callback_data": "edit_slot_duration"}],
                    [{"text": "⏳ Буфер до", "callback_data": "edit_buffer_before"}, {"text": "⏳ Буфер после", "callback_data": "edit_buffer_after"}],
                    [{"text": "⏸ Перерывы", "callback_data": "manage_breaks_global"}],
                    [{"text": "🗓 График работы", "callback_data": "admin_cal_0"}],
                    [{"text": "📋 Просмотр записей", "callback_data": "admin_bookings_cal_0"}],
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
    dates_in_week = [d for d in dates_in_week if d >= today]
    
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DailySchedule).where(DailySchedule.date >= dates_in_week[0], DailySchedule.date <= dates_in_week[-1], DailySchedule.is_day_off == True)
            )
            days_off = {do.date for do in result.scalars()}
            
        ru_days = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
        
        inline_keyboard = []
        for d in dates_in_week:
            is_off = d in days_off
            marker = "🔴" if is_off else "🟢"
            day_name = ru_days[d.weekday()]
            btn_text = f"{marker} {d.strftime('%d.%m')} ({day_name})"
            cb_data = f"edit_day_{week_offset}_{d.strftime('%Y-%m-%d')}"
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

async def send_day_settings(chat_id: int, week_offset: int, date_str: str, bot_token: str, message_id: int = None):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    url_edit_message = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(DailySchedule).where(DailySchedule.date == target_date))
            day_schedule = result.scalar_one_or_none()
            
            result_global = await session.execute(select(StudioSettings).where(StudioSettings.id == 1))
            studio_settings = result_global.scalar_one_or_none()
            
        is_off = day_schedule.is_day_off if day_schedule else False
        status_text = "Выходной" if is_off else "Рабочий"
        
        open_time = (day_schedule.open_time if day_schedule and day_schedule.open_time else studio_settings.open_time) if not is_off else "-"
        close_time = (day_schedule.close_time if day_schedule and day_schedule.close_time else studio_settings.close_time) if not is_off else "-"
        slot_duration = (day_schedule.slot_duration if day_schedule and day_schedule.slot_duration else studio_settings.slot_duration) if not is_off else "-"
        
        text = (
            f"📅 *Настройки дня: {target_date.strftime('%d.%m.%Y')}*\n"
            f"Статус: {status_text}\n\n"
        )
        if not is_off:
            text += (
                f"Открытие: {open_time}\n"
                f"Закрытие: {close_time}\n"
                f"Длительность слота: {slot_duration}\n"
            )
            
        custom_breaks = day_schedule.custom_breaks if day_schedule and day_schedule.custom_breaks else "Нет"
        if not is_off:
            text += f"Доп. перерывы: {custom_breaks}\n"
            
        inline_keyboard = []
        if is_off:
            inline_keyboard.append([{"text": "🟢 Сделать рабочим", "callback_data": f"toggle_day_off_{week_offset}_{date_str}"}])
        else:
            inline_keyboard.append([{"text": "🔴 Сделать выходным", "callback_data": f"toggle_day_off_{week_offset}_{date_str}"}])
            inline_keyboard.append([{"text": "🕒 Изменить время", "callback_data": f"day_time_menu_{week_offset}_{date_str}"}])
        
        inline_keyboard.append([{"text": "🔄 Сбросить к стандартным", "callback_data": f"reset_day_{week_offset}_{date_str}"}])
        inline_keyboard.append([{"text": "🔙 Назад в календарь", "callback_data": f"admin_cal_{week_offset}"}])
        
        keyboard = {"inline_keyboard": inline_keyboard}
        
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
        logger.error(f"Error sending day settings: {e}")

async def send_day_time_menu(chat_id: int, week_offset: int, date_str: str, bot_token: str, message_id: int = None):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    url_edit_message = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    
    text = f"🕒 *Настройки времени для {date_str}*\nВыберите параметр:"
    
    inline_keyboard = [
        [{"text": "🌅 Открытие", "callback_data": f"edit_day_open_time_{date_str}"}, {"text": "🌃 Закрытие", "callback_data": f"edit_day_close_time_{date_str}"}],
        [{"text": "⏱ Длительность", "callback_data": f"edit_day_slot_duration_{date_str}"}],
        [{"text": "⏸ Перерывы", "callback_data": f"manage_breaks_day_{date_str}"}],
        [{"text": "🔙 Назад", "callback_data": f"edit_day_{week_offset}_{date_str}"}]
    ]
    keyboard = {"inline_keyboard": inline_keyboard}
    
    try:
        async with httpx.AsyncClient() as client:
            if message_id:
                await client.post(url_edit_message, json={"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
            else:
                await client.post(url_send_message, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
    except Exception as e:
        logger.error(f"Error sending day time menu: {e}")

async def handle_admin_callback(chat_id: int, data: str, bot_token: str):
    field_to_edit = data.replace("edit_", "").replace("day_", "")
    
    # if it's a day edit, data ends with _YYYY-MM-DD
    if data.startswith("edit_day_"):
        parts = data.split("_")
        date_str = parts[-1]
        field_name = "_".join(parts[2:-1])
        admin_states[chat_id] = f"{field_name}_{date_str}"
        prompt_key = field_name
    elif data in ["edit_open_time", "edit_close_time", "edit_slot_duration", "edit_buffer_before", "edit_buffer_after", "add_break_global"]:
        field = data.replace("edit_", "")
        admin_states[chat_id] = field
        prompt_key = field
    elif data.startswith("add_break_"):
        date_str = data.split("_")[-1]
        admin_states[chat_id] = f"add_break_{date_str}"
        prompt_key = "add_break"
    else:
        admin_states[chat_id] = field_to_edit
        prompt_key = field_to_edit
    
    prompt_text = PROMPTS.get(prompt_key, f"Отправьте новое значение для параметра `{prompt_key}`:")
    
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
        
    state_val = admin_states[chat_id]
    
    try:
        async with AsyncSessionLocal() as session:
            # Check if it's a daily override
            if "_" in state_val and state_val[-10:].count("-") == 2:
                # Format: field_name_YYYY-MM-DD
                date_str = state_val[-10:]
                field_to_edit = state_val[:-11]
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                result = await session.execute(select(DailySchedule).where(DailySchedule.date == target_date))
                daily_schedule = result.scalar_one_or_none()
                if not daily_schedule:
                    daily_schedule = DailySchedule(date=target_date)
                    session.add(daily_schedule)
                
                if field_to_edit == "slot_duration":
                    setattr(daily_schedule, field_to_edit, int(text))
                    redirect_target = "day"
                elif field_to_edit == "add_break":
                    existing = daily_schedule.custom_breaks
                    if existing:
                        daily_schedule.custom_breaks = f"{existing}, {text}"
                    else:
                        daily_schedule.custom_breaks = text
                    redirect_target = "day_breaks"
                else:
                    setattr(daily_schedule, field_to_edit, text)
                    redirect_target = "day"
                    
                await session.commit()
                redirect_date = date_str
            else:
                field_to_edit = state_val
                result = await session.execute(select(StudioSettings).where(StudioSettings.id == 1))
                studio_settings = result.scalar_one_or_none()
                
                if studio_settings:
                    if field_to_edit in ["slot_duration", "buffer_before", "buffer_after"]:
                        setattr(studio_settings, field_to_edit, int(text))
                        redirect_target = "global"
                    elif field_to_edit == "add_break_global":
                        existing = studio_settings.custom_breaks
                        if existing:
                            studio_settings.custom_breaks = f"{existing}, {text}"
                        else:
                            studio_settings.custom_breaks = text
                        redirect_target = "global_breaks"
                    else:
                        setattr(studio_settings, field_to_edit, text)
                        redirect_target = "global"
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
            
        if redirect_target == "global":
            await send_admin_panel(chat_id, bot_token)
        elif redirect_target == "global_breaks":
            await send_breaks_menu(chat_id, bot_token)
        elif redirect_target == "day_breaks":
            await send_breaks_menu(chat_id, bot_token, date_str=redirect_date)
        else:
            await send_day_settings(chat_id, 0, redirect_date, bot_token)  # week_offset = 0 for simplicity
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

async def send_admin_bookings_calendar(chat_id: int, week_offset: int, bot_token: str, message_id: int = None):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    url_edit_message = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    dates_in_week = [start_of_week + timedelta(days=i) for i in range(7)]
    dates_in_week = [d for d in dates_in_week if d >= today]
    
    try:
        from bot_service.models.bookings import Booking
        from sqlalchemy import func
        async with AsyncSessionLocal() as session:
            start_dt = datetime.combine(dates_in_week[0], datetime.min.time())
            end_dt = datetime.combine(dates_in_week[-1], datetime.max.time())
            
            result = await session.execute(
                select(func.date(Booking.session_start), func.count(Booking.id))
                .where(Booking.session_start >= start_dt, Booking.session_start <= end_dt)
                .group_by(func.date(Booking.session_start))
            )
            bookings_count = {datetime.strptime(row[0], "%Y-%m-%d").date(): row[1] for row in result.all()}
            
        ru_days = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
        
        inline_keyboard = []
        for d in dates_in_week:
            d_str = d.strftime("%Y-%m-%d")
            count = bookings_count.get(d, 0)
            marker = "📝" if count > 0 else "📭"
            day_name = ru_days[d.weekday()]
            btn_text = f"{marker} {d.strftime('%d.%m')} ({day_name}) - {count} зап."
            cb_data = f"view_day_bookings_{d_str}"
            inline_keyboard.append([{"text": btn_text, "callback_data": cb_data}])
            
        nav_row = []
        if week_offset > 0:
            nav_row.append({"text": "⬅️ Назад", "callback_data": f"admin_bookings_cal_{week_offset-1}"})
        nav_row.append({"text": "Вперед ➡️", "callback_data": f"admin_bookings_cal_{week_offset+1}"})
        
        inline_keyboard.append(nav_row)
        inline_keyboard.append([{"text": "🔙 В настройки", "callback_data": "admin_panel"}])
        
        keyboard = {"inline_keyboard": inline_keyboard}
        text = f"📋 *Календарь записей*\n\nНеделя: {dates_in_week[0].strftime('%d.%m')} - {dates_in_week[-1].strftime('%d.%m')}\nВыберите день для просмотра записей:"
        
        async with httpx.AsyncClient() as client:
            if message_id:
                await client.post(url_edit_message, json={"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
            else:
                await client.post(url_send_message, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
    except Exception as e:
        logger.error(f"Error sending admin bookings calendar: {e}")

async def send_day_bookings(chat_id: int, date_str: str, bot_token: str, message_id: int = None):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    url_edit_message = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())
    
    try:
        from bot_service.models.bookings import Booking
        from bot_service.models.users import User
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Booking, User).join(User, Booking.user_id == User.id)
                .where(Booking.session_start >= start_dt, Booking.session_start <= end_dt)
                .order_by(Booking.session_start)
            )
            bookings = result.all()
            
        inline_keyboard = []
        for booking, user in bookings:
            time_str = booking.session_start.strftime("%H:%M")
            btn_text = f"⏰ {time_str} - {user.full_name}"
            cb_data = f"view_booking_{booking.id}"
            inline_keyboard.append([{"text": btn_text, "callback_data": cb_data}])
            
        inline_keyboard.append([{"text": "🔙 В календарь записей", "callback_data": "admin_bookings_cal_0"}])
        keyboard = {"inline_keyboard": inline_keyboard}
        
        text = f"📋 *Записи на {target_date.strftime('%d.%m.%Y')}*\n"
        if not bookings:
            text += "\nНа этот день пока нет записей."
            
        async with httpx.AsyncClient() as client:
            if message_id:
                await client.post(url_edit_message, json={"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
            else:
                await client.post(url_send_message, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
    except Exception as e:
        logger.error(f"Error sending day bookings: {e}")

async def send_booking_details(chat_id: int, booking_id: int, bot_token: str, message_id: int = None):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    url_edit_message = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    
    try:
        from bot_service.models.bookings import Booking
        from bot_service.models.users import User
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Booking, User).join(User, Booking.user_id == User.id)
                .where(Booking.id == booking_id)
            )
            row = result.first()
            if not row:
                return
            booking, user = row
            
        date_str = booking.session_start.strftime("%Y-%m-%d")
        
        text = (
            f"👤 *Детали записи*\n\n"
            f"Клиент: {user.full_name}\n"
            f"ID в Telegram: {user.telegram_id}\n"
            f"Дата: {booking.session_start.strftime('%d.%m.%Y')}\n"
            f"Время: {booking.session_start.strftime('%H:%M')}\n"
            f"Тип: {'Пробная тренировка' if booking.is_trial else 'Регулярная тренировка'}\n"
            f"Статус: {booking.status}\n"
        )
        
        inline_keyboard = [
            [{"text": "🔙 Назад к списку", "callback_data": f"view_day_bookings_{date_str}"}]
        ]
        keyboard = {"inline_keyboard": inline_keyboard}
        
        async with httpx.AsyncClient() as client:
            if message_id:
                await client.post(url_edit_message, json={"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
            else:
                await client.post(url_send_message, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
    except Exception as e:
        logger.error(f"Error sending booking details: {e}")

async def send_breaks_menu(chat_id: int, bot_token: str, date_str: str = None, message_id: int = None):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    url_edit_message = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    
    try:
        async with AsyncSessionLocal() as session:
            if date_str:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                result = await session.execute(select(DailySchedule).where(DailySchedule.date == target_date))
                record = result.scalar_one_or_none()
                text = f"⏸ *Перерывы на {date_str}*\n\nНажмите на перерыв, чтобы удалить его:"
                back_callback = f"day_time_menu_0_{date_str}"
                add_callback = f"add_break_{date_str}"
                del_prefix = f"del_break_day_{date_str}_"
            else:
                result = await session.execute(select(StudioSettings).where(StudioSettings.id == 1))
                record = result.scalar_one_or_none()
                text = "⏸ *Глобальные перерывы*\n\nНажмите на перерыв, чтобы удалить его:"
                back_callback = "admin_panel"
                add_callback = "add_break_global"
                del_prefix = "del_break_global_"
                
        breaks_str = record.custom_breaks if record and record.custom_breaks else ""
        breaks_list = [b.strip() for b in breaks_str.split(",") if b.strip()]
        
        inline_keyboard = []
        for i, br in enumerate(breaks_list):
            inline_keyboard.append([{"text": f"❌ {br}", "callback_data": f"{del_prefix}{i}"}])
            
        inline_keyboard.append([{"text": "➕ Добавить перерыв", "callback_data": add_callback}])
        inline_keyboard.append([{"text": "🔙 Назад", "callback_data": back_callback}])
        
        keyboard = {"inline_keyboard": inline_keyboard}
        
        async with httpx.AsyncClient() as client:
            if message_id:
                await client.post(url_edit_message, json={"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
            else:
                await client.post(url_send_message, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "reply_markup": keyboard})
    except Exception as e:
        logger.error(f"Error sending breaks menu: {e}")
