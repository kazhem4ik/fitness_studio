from datetime import date as dt_date, time as dt_time, datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.core.config import settings
from planner_service.core.database import get_db
from planner_service.core.security import decode_access_token
from planner_service.models.appointment import Appointment
from planner_service.models.client import Client
from planner_service.models.package import Package

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

COOKIE_NAME = "planner_token"


async def check_buffer_conflict(
    db: AsyncSession,
    appt_date: dt_date,
    appt_time_start: dt_time,
    appt_time_end: dt_time,
    trainer_id: int,
    exclude_id: Optional[int] = None,
) -> Optional[str]:
    """
    Проверяет, не пересекается ли окно брони новой записи с существующими.
    Окно = [time_start - buffer_before, time_end + buffer_after].
    Возвращает None если конфликта нет, или строку с ближайшим свободным временем если конфликт есть.
    """
    buf_before = timedelta(minutes=settings.BUFFER_BEFORE)
    buf_after = timedelta(minutes=settings.BUFFER_AFTER)

    new_win_start = datetime.combine(appt_date, appt_time_start) - buf_before
    new_win_end = datetime.combine(appt_date, appt_time_end) + buf_after

    query = select(Appointment).join(Client, Appointment.client_id == Client.id).where(
        and_(
            Appointment.date == appt_date,
            Appointment.is_cancelled == False,
            Appointment.trainer_id == trainer_id,
            Client.deleted_at.is_(None),
        )
    )
    if exclude_id:
        query = query.where(Appointment.id != exclude_id)

    result = await db.execute(query)
    existing = result.scalars().all()

    for appt in existing:
        win_start = datetime.combine(appt.date, appt.time_start) - buf_before
        win_end = datetime.combine(appt.date, appt.time_end) + buf_after
        if new_win_start < win_end and new_win_end > win_start:
            earliest = (datetime.combine(appt.date, appt.time_end) + buf_after + buf_before)
            return earliest.strftime("%H:%M")
    return None


# --- Auth dependency ---

async def require_auth(request: Request):
    """Проверка авторизации. Возвращает payload токена."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Токен истёк")
    return payload


# --- Schemas ---

class AppointmentCreate(BaseModel):
    client_name: str
    client_phone: Optional[str] = None
    date: dt_date
    time_start: dt_time
    time_end: dt_time
    training_type: Optional[str] = None
    notes: Optional[str] = None
    is_confirmed: bool = True


class AppointmentUpdate(BaseModel):
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    date: Optional[dt_date] = None
    time_start: Optional[dt_time] = None
    time_end: Optional[dt_time] = None
    training_type: Optional[str] = None
    notes: Optional[str] = None
    is_confirmed: Optional[bool] = None
    is_cancelled: Optional[bool] = None


class AppointmentResponse(BaseModel):
    id: int
    client_id: Optional[int]
    client_name: str
    client_phone: Optional[str]
    date: dt_date
    time_start: dt_time
    time_end: dt_time
    training_type: Optional[str]
    notes: Optional[str]
    price: Optional[float]
    is_paid: bool
    payment_method: Optional[str]
    is_confirmed: bool
    is_cancelled: bool
    is_attended: bool
    is_no_show: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class AttendanceUpdate(BaseModel):
    status: str  # "no_show", "attended", "pending"


# --- Endpoints ---

@router.get("", response_model=List[AppointmentResponse])
async def get_appointments(
    target_date: Optional[dt_date] = None,
    date_from: Optional[dt_date] = None,
    date_to: Optional[dt_date] = None,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """
    Получить записи текущего тренера.
    - target_date: записи на конкретный день
    - date_from + date_to: записи за диапазон дат
    """
    trainer_id = int(auth["sub"])

    query = select(Appointment).join(Client, Appointment.client_id == Client.id).where(
        and_(
            Appointment.is_cancelled == False,
            Appointment.trainer_id == trainer_id,
            Client.deleted_at.is_(None),
        )
    )

    if target_date:
        query = query.where(Appointment.date == target_date)
    elif date_from and date_to:
        query = query.where(and_(Appointment.date >= date_from, Appointment.date <= date_to))

    query = query.order_by(Appointment.date, Appointment.time_start)
    result = await db.execute(query)
    appointments = result.scalars().all()

    # Auto-deduction for passed appointments
    local_now = datetime.now()
    changed = False
    for appt in appointments:
        if not appt.is_attended and not appt.is_cancelled and not appt.is_no_show:
            appt_dt = datetime.combine(appt.date, appt.time_end)
            if appt_dt < local_now:
                appt.is_attended = True
                if appt.client_id:
                    client_res = await db.execute(select(Client).where(Client.id == appt.client_id))
                    client = client_res.scalar_one_or_none()
                    if client and client.sessions_balance > 0:
                        client.sessions_balance -= 1
                changed = True

    if changed:
        await db.commit()

    return appointments


@router.post("", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    data: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Создать новую запись клиента."""
    trainer_id = int(auth["sub"])

    # Проверка буфера времени
    conflict_time = await check_buffer_conflict(
        db, data.date, data.time_start, data.time_end, trainer_id
    )
    if conflict_time:
        raise HTTPException(
            status_code=409,
            detail=f"Конфликт времени. С учётом перерыва между занятиями ближайшее доступное время: {conflict_time}"
        )

    # Ищем клиента этого тренера по имени
    client_query = select(Client).where(
        Client.full_name == data.client_name,
        Client.trainer_id == trainer_id,
    )
    client_result = await db.execute(client_query)
    client = client_result.scalar_one_or_none()
    
    if client and client.deleted_at is not None:
        raise HTTPException(
            status_code=400,
            detail="Данный клиент находится в корзине. Восстановите его в разделе 'Клиенты' (иконка корзины), либо используйте другое имя."
        )

    if not client:
        client = Client(
            full_name=data.client_name,
            phone=data.client_phone,
            trainer_id=trainer_id,
        )
        db.add(client)
        await db.commit()
        await db.refresh(client)

    appt_data = data.model_dump()
    appt_data["client_id"] = client.id
    appt_data["trainer_id"] = trainer_id

    appointment = Appointment(**appt_data)
    db.add(appointment)

    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.get("/clients", response_model=List[str])
async def get_client_names(
    q: str = "",
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Автоподсказки имён клиентов для текущего тренера."""
    trainer_id = int(auth["sub"])
    query = select(Appointment.client_name).distinct().where(
        Appointment.trainer_id == trainer_id
    )
    if q:
        query = query.where(Appointment.client_name.ilike(f"%{q}%"))
    query = query.order_by(Appointment.client_name).limit(20)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Получить запись по ID (только своя)."""
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.trainer_id == trainer_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return appointment


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: int,
    data: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Обновить запись (только свою)."""
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.trainer_id == trainer_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    update_data = data.model_dump(exclude_unset=True)

    new_date = update_data.get("date", appointment.date)
    new_time_start = update_data.get("time_start", appointment.time_start)
    new_time_end = update_data.get("time_end", appointment.time_end)
    if "date" in update_data or "time_start" in update_data or "time_end" in update_data:
        conflict_time = await check_buffer_conflict(
            db, new_date, new_time_start, new_time_end, trainer_id, exclude_id=appointment_id
        )
        if conflict_time:
            raise HTTPException(
                status_code=409,
                detail=f"Конфликт времени. С учётом перерыва между занятиями ближайшее доступное время: {conflict_time}"
            )

    for key, value in update_data.items():
        setattr(appointment, key, value)

    # Синхронизация клиента
    if "client_name" in update_data or "client_phone" in update_data:
        client_query = select(Client).where(
            Client.full_name == appointment.client_name,
            Client.trainer_id == trainer_id,
        )
        client_result = await db.execute(client_query)
        client = client_result.scalar_one_or_none()

        if client and client.deleted_at is not None:
            raise HTTPException(
                status_code=400,
                detail="Данный клиент находится в корзине. Восстановите его в разделе 'Клиенты' (иконка корзины), либо используйте другое имя."
            )

        if not client:
            client = Client(
                full_name=appointment.client_name,
                phone=appointment.client_phone,
                trainer_id=trainer_id,
            )
            db.add(client)
            await db.commit()
            await db.refresh(client)
        else:
            if appointment.client_phone and client.phone != appointment.client_phone:
                client.phone = appointment.client_phone
                await db.commit()

        appointment.client_id = client.id

    appointment.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.patch("/{appointment_id}/attendance", response_model=AppointmentResponse)
async def update_attendance(
    appointment_id: int,
    data: AttendanceUpdate,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Обновить статус посещаемости (Не пришёл / Пришёл / Запланировано)."""
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.trainer_id == trainer_id,
        )
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    client = None
    if appt.client_id:
        client_res = await db.execute(select(Client).where(Client.id == appt.client_id))
        client = client_res.scalar_one_or_none()

    was_deducted = appt.is_attended
    
    if data.status == "no_show":
        appt.is_no_show = True
        appt.is_attended = False
    elif data.status == "attended":
        appt.is_attended = True
        appt.is_no_show = False
    elif data.status == "pending":
        appt.is_attended = False
        appt.is_no_show = False
    else:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    is_deducted = appt.is_attended
    
    if client:
        if was_deducted and not is_deducted:
            client.sessions_balance += 1
        elif not was_deducted and is_deducted:
            if client.sessions_balance > 0:
                client.sessions_balance -= 1

    appt.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(appt)
    return appt


@router.delete("/{appointment_id}")
async def delete_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Удалить запись (мягкое удаление — отмена)."""
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.trainer_id == trainer_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    appointment.is_cancelled = True
    appointment.updated_at = datetime.utcnow()
    await db.commit()
    return {"success": True, "message": "Запись отменена"}


@router.delete("/{appointment_id}/permanent")
async def permanently_delete_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_auth),
):
    """Полное удаление записи из БД."""
    trainer_id = int(auth["sub"])
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.trainer_id == trainer_id,
        )
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    await db.delete(appointment)
    await db.commit()
    return {"success": True, "message": "Запись удалена навсегда"}




