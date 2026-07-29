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
from planner_service.models.admin import AdminUser
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
    trainer_id: int


def format_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    if len(digits) == 11 and digits.startswith("7"):
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return phone


@router.get("/trainers")
async def get_trainers(db: AsyncSession = Depends(get_db)):
    """Публичный список активных тренеров для страницы записи."""
    result = await db.execute(
        select(AdminUser).where(
            AdminUser.is_active == 1,
            AdminUser.role == "trainer"
        ).order_by(AdminUser.display_name)
    )
    trainers = result.scalars().all()
    return [{"id": t.id, "display_name": t.display_name} for t in trainers]


@router.get("/slots", response_model=List[SlotResponse])
async def get_slots(d: date, trainer_id: int, db: AsyncSession = Depends(get_db)):
    """Свободные слоты на дату для конкретного тренера."""
    open_hour, open_minute = map(int, settings.STUDIO_OPEN_TIME.split(':'))
    close_hour, close_minute = map(int, settings.STUDIO_CLOSE_TIME.split(':'))

    start_time = datetime(d.year, d.month, d.day, open_hour, open_minute)
    end_time = datetime(d.year, d.month, d.day, close_hour, close_minute)

    result = await db.execute(
        select(Appointment).join(Client, Appointment.client_id == Client.id).where(
            Appointment.date == d,
            Appointment.trainer_id == trainer_id,
            Appointment.is_cancelled == False,
            Client.deleted_at.is_(None)
        )
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
        available = True
        for (occ_start, occ_end) in occupied_times:
            if current_time < occ_end and slot_end > occ_start:
                available = False
                break
        if current_time < datetime.now() + timedelta(hours=1):
            available = False
        if available:
            slots.append(SlotResponse(time=current_time.strftime("%H:%M"), available=True))
        current_time += timedelta(minutes=settings.SLOT_DURATION)

    return slots


@router.post("/book")
async def create_booking(req: BookingRequest, db: AsyncSession = Depends(get_db)):
    """Записать клиента к конкретному тренеру."""
    formatted_phone = format_phone(req.client_phone)
    if not formatted_phone:
        raise HTTPException(status_code=400, detail="Неверный формат телефона")

    trainer_res = await db.execute(
        select(AdminUser).where(AdminUser.id == req.trainer_id, AdminUser.is_active == 1)
    )
    trainer = trainer_res.scalar_one_or_none()
    if not trainer:
        raise HTTPException(status_code=404, detail="Тренер не найден")

    result = await db.execute(
        select(Client).where(Client.phone == formatted_phone, Client.trainer_id == req.trainer_id)
    )
    client = result.scalars().first()

    is_new = False
    if not client:
        client = Client(
            full_name=req.client_name,
            phone=formatted_phone,
            is_active=True,
            trainer_id=req.trainer_id,
        )
        db.add(client)
        await db.flush()
        is_new = True
    elif client.deleted_at is not None:
        client.deleted_at = None
        client.full_name = req.client_name # update name
        await db.flush()
        is_new = True

    try:
        app_date = datetime.strptime(req.date, "%Y-%m-%d").date()
        start_time = datetime.strptime(req.time, "%H:%M").time()
        dt_start = datetime.combine(app_date, start_time)
        dt_end = dt_start + timedelta(minutes=settings.SLOT_DURATION)
        end_time = dt_end.time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты или времени")

    conflict = await db.execute(
        select(Appointment).join(Client, Appointment.client_id == Client.id).where(
            Appointment.date == app_date,
            Appointment.trainer_id == req.trainer_id,
            Appointment.time_start < end_time,
            Appointment.time_end > start_time,
            Appointment.is_cancelled == False,
            Client.deleted_at.is_(None)
        )
    )
    if conflict.scalars().first():
        raise HTTPException(status_code=400, detail="К сожалению, это время уже занято")

    appointment = Appointment(
        trainer_id=req.trainer_id,
        client_id=client.id,
        client_name=client.full_name,
        client_phone=formatted_phone,
        date=app_date,
        time_start=start_time,
        time_end=end_time,
        training_type="Персональная",
        price=0.0
    )
    db.add(appointment)
    await db.commit()

    msg_title = "Новая запись!"
    msg_body = f"{req.client_name} ({formatted_phone}) записался на {req.date} в {req.time}"
    if is_new:
        msg_body += " (Новый клиент)"

    await send_push_notification(db, msg_title, msg_body, trainer_id=req.trainer_id)
    return {"status": "ok", "message": "Вы успешно записаны!", "client_id": client.id}
