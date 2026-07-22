import re
from datetime import datetime, date, timedelta
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.core.database import get_db
from planner_service.core.config import settings
from planner_service.models.client import Client
from planner_service.models.appointment import Appointment
from planner_service.core.push import send_push_notification

router = APIRouter(tags=["Public Booking"])

class SlotResponse(BaseModel):
    time: str
    available: bool

class BookingRequest(BaseModel):
    date: str
    time: str
    client_name: str
    client_phone: str


def format_phone(phone: str) -> str:
    """Оставляет только цифры, если начинается с 7 или 8, приводит к +7..."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    
    if len(digits) == 11 and digits.startswith("7"):
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    
    return phone # Если не российский номер, оставляем как есть


@router.get("/slots", response_model=List[SlotResponse])
async def get_slots(
    d: date,
    db: AsyncSession = Depends(get_db)
):
    # Генерация слотов
    open_hour, open_minute = map(int, settings.STUDIO_OPEN_TIME.split(':'))
    close_hour, close_minute = map(int, settings.STUDIO_CLOSE_TIME.split(':'))
    
    start_time = datetime(d.year, d.month, d.day, open_hour, open_minute)
    end_time = datetime(d.year, d.month, d.day, close_hour, close_minute)
    
    # Получаем занятые слоты на этот день
    result = await db.execute(
        select(Appointment).where(Appointment.date == d)
    )
    appointments = result.scalars().all()
    
    occupied_times = []
    for appt in appointments:
        app_start = datetime(d.year, d.month, d.day, appt.time_start.hour, appt.time_start.minute)
        app_end = datetime(d.year, d.month, d.day, appt.time_end.hour, appt.time_end.minute)
        occupied_times.append((app_start, app_end))
    
    slots = []
    current_time = start_time
    while current_time + timedelta(minutes=settings.SLOT_DURATION) <= end_time:
        slot_end = current_time + timedelta(minutes=settings.SLOT_DURATION)
        
        # Проверяем пересечения
        available = True
        for (occ_start, occ_end) in occupied_times:
            if current_time < occ_end and slot_end > occ_start:
                available = False
                break
        
        # Нельзя записаться на прошедшее время
        if current_time < datetime.now() + timedelta(hours=1):
            available = False
            
        if available:
            slots.append(SlotResponse(time=current_time.strftime("%H:%M"), available=True))
            
        current_time += timedelta(minutes=settings.SLOT_DURATION)
        
    return slots


@router.post("/book")
async def create_booking(
    req: BookingRequest,
    db: AsyncSession = Depends(get_db)
):
    formatted_phone = format_phone(req.client_phone)
    if not formatted_phone:
        raise HTTPException(status_code=400, detail="Неверный формат телефона")
        
    # Ищем клиента
    result = await db.execute(
        select(Client).where(Client.phone == formatted_phone)
    )
    client = result.scalars().first()
    
    is_new = False
    if not client:
        # Создаем нового клиента
        client = Client(
            full_name=req.client_name,
            phone=formatted_phone,
            is_active=True
        )
        db.add(client)
        await db.flush()
        is_new = True
        
    # Парсим время
    try:
        app_date = datetime.strptime(req.date, "%Y-%m-%d").date()
        time_parts = req.time.split(":")
        start_time = datetime.strptime(req.time, "%H:%M").time()
        
        # Считаем конец тренировки
        dt_start = datetime.combine(app_date, start_time)
        dt_end = dt_start + timedelta(minutes=settings.SLOT_DURATION)
        end_time = dt_end.time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты или времени")
        
    # Проверяем, не занято ли уже время
    conflict = await db.execute(
        select(Appointment).where(
            Appointment.date == app_date,
            Appointment.time_start < end_time,
            Appointment.time_end > start_time
        )
    )
    if conflict.scalars().first():
        raise HTTPException(status_code=400, detail="К сожалению, это время уже занято")
        
    # Создаем запись
    appointment = Appointment(
        client_id=client.id,
        date=app_date,
        time_start=start_time,
        time_end=end_time,
        training_type="Персональная",
        status="scheduled",
        price=0.0
    )
    db.add(appointment)
    await db.commit()
    
    # Отправляем push-уведомление админу
    msg_title = "Новая запись!"
    msg_body = f"{req.client_name} ({formatted_phone}) записался на {req.date} в {req.time}"
    if is_new:
        msg_body += " (Новый клиент)"
        
    await send_push_notification(db, msg_title, msg_body)
    
    return {"status": "ok", "message": "Вы успешно записаны!", "client_id": client.id}
