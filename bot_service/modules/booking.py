import httpx
import logging
from datetime import datetime, timedelta, time
from sqlalchemy import select
from bot_service.core.database import AsyncSessionLocal
from bot_service.models.users import User
from bot_service.models.bookings import Booking
from bot_service.models.settings import StudioSettings
from bot_service.models.daily_schedule import DailySchedule
from bot_service.core.config import settings

logger = logging.getLogger(__name__)

async def handle_booking_request(chat_id: int, bot_token: str):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        today = datetime.now().date()
        end_date = today + timedelta(days=14)
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DailySchedule).where(DailySchedule.date > today, DailySchedule.date <= end_date, DailySchedule.is_day_off == True)
            )
            days_off = {do.date for do in result.scalars()}
            
        inline_keyboard = []
        row = []
        for i in range(1, 15):  # 14 days ahead
            date_obj = today + timedelta(days=i)
            date_str = date_obj.strftime("%Y-%m-%d")
            display_date = date_obj.strftime("%d.%m")
            
            if date_obj in days_off:
                btn = {"text": f"❌ {display_date}", "callback_data": "day_off"}
            else:
                btn = {"text": f"📅 {display_date}", "callback_data": f"date_{date_str}"}
                
            row.append(btn)
            if len(row) == 2:
                inline_keyboard.append(row)
                row = []
        if row:
            inline_keyboard.append(row)
            
        keyboard = {"inline_keyboard": inline_keyboard}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url_send_message,
                json={
                    "chat_id": chat_id,
                    "text": "Выберите дату для пробной тренировки (на ближайшие 2 недели):",
                    "reply_markup": keyboard
                }
            )
            response.raise_for_status()
            logger.info(f"Sent date options to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send date options to {chat_id}: {e}")

async def handle_booking_slots(chat_id: int, date_str: str, bot_token: str):
    url_send_message = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        logger.error(f"Invalid date format received: {date_str}")
        return
        
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(StudioSettings).where(StudioSettings.id == 1))
            studio_settings = result.scalar_one_or_none()
            if not studio_settings:
                logger.error("StudioSettings not found in database")
                return
                
            result_day = await session.execute(select(DailySchedule).where(DailySchedule.date == target_date))
            day_schedule = result_day.scalar_one_or_none()
            
            if day_schedule and day_schedule.is_day_off:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        url_send_message,
                        json={
                            "chat_id": chat_id,
                            "text": "К сожалению, в этот день студия не работает. Выберите другой день."
                        }
                    )
                return

            start_of_day = datetime.combine(target_date, time.min)
            end_of_day = datetime.combine(target_date, time.max)
            
            result = await session.execute(
                select(Booking).where(Booking.session_start >= start_of_day, Booking.session_start <= end_of_day)
            )
            booked_times = [b.session_start for b in result.scalars()]
            
            open_time_str = day_schedule.open_time if day_schedule and day_schedule.open_time else studio_settings.open_time
            close_time_str = day_schedule.close_time if day_schedule and day_schedule.close_time else studio_settings.close_time
            slot_duration_val = day_schedule.slot_duration if day_schedule and day_schedule.slot_duration else studio_settings.slot_duration
            
            open_time = datetime.strptime(open_time_str, "%H:%M").time()
            close_time = datetime.strptime(close_time_str, "%H:%M").time()
            
            current_dt = datetime.combine(target_date, open_time)
            close_dt = datetime.combine(target_date, close_time)
            
            parsed_custom_breaks = []
            breaks_str = ""
            if day_schedule and day_schedule.custom_breaks is not None:
                breaks_str = day_schedule.custom_breaks
            elif studio_settings and studio_settings.custom_breaks is not None:
                breaks_str = studio_settings.custom_breaks
                
            if breaks_str:
                for br in breaks_str.split(","):
                    br = br.strip()
                    if "-" in br:
                        try:
                            start_str, end_str = br.split("-")
                            b_start = datetime.strptime(start_str.strip(), "%H:%M").time()
                            b_end = datetime.strptime(end_str.strip(), "%H:%M").time()
                            parsed_custom_breaks.append((
                                datetime.combine(target_date, b_start),
                                datetime.combine(target_date, b_end)
                            ))
                        except Exception as e:
                            logger.error(f"Failed to parse custom break '{br}': {e}")
            
            available_slots = []
            slot_delta = timedelta(minutes=slot_duration_val)
            
            while current_dt + slot_delta <= close_dt:
                slot_end = current_dt + slot_delta
                
                # Check custom breaks overlap
                overlap_break = False
                for b_start, b_end in parsed_custom_breaks:
                    if current_dt < b_end and slot_end > b_start:
                        current_dt = b_end
                        overlap_break = True
                        break
                if overlap_break:
                    continue
                    
                # Check against bookings
                is_booked = False
                for b_time in booked_times:
                    if current_dt <= b_time < slot_end or current_dt < b_time + slot_delta <= slot_end:
                        is_booked = True
                        break
                        
                if not is_booked:
                    available_slots.append(current_dt)
                    
                current_dt = slot_end
                
            if not available_slots:
                text = f"К сожалению, на {target_date.strftime('%d.%m.%Y')} все окна заняты. Попробуйте выбрать другую дату."
                keyboard = None
            else:
                text = f"Доступные окна на {target_date.strftime('%d.%m.%Y')}:"
                inline_keyboard = []
                row = []
                for slot_dt in available_slots:
                    time_str = slot_dt.strftime("%H:%M")
                    row.append({"text": time_str, "callback_data": f"slot_{date_str}_{time_str}"})
                    if len(row) == 2:
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
            logger.info(f"Sent slot options for {date_str} to {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send slot options to {chat_id}: {e}")

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
                # slot_data format: slot_YYYY-MM-DD_HH:MM
                parts = slot_data.split("_")
                date_str = parts[1]
                time_str = parts[2]
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                target_time = datetime.strptime(time_str, "%H:%M").time()
                session_time = datetime.combine(target_date, target_time)
            except (IndexError, ValueError) as e:
                logger.error(f"Invalid slot data format '{slot_data}': {e}")
                return
            
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
