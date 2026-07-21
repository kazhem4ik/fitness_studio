from datetime import date, time, datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.core.config import settings
from planner_service.core.database import get_db
from planner_service.core.security import decode_access_token
from planner_service.models.appointment import Appointment

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

COOKIE_NAME = "planner_token"


async def check_buffer_conflict(
    db: AsyncSession,
    appt_date: date,
    appt_time_start: time,
    appt_time_end: time,
    exclude_id: Optional[int] = None,
) -> Optional[str]:
    """
    Проверяет, не пересекается ли окно брони новой записи с существующими.
    Окно = [time_start - buffer_before, time_end + buffer_after].
    Возвращает None если конфликта нет, или строку с ближайшим свободным временем если конфликт есть.
    """
    buf_before = timedelta(minutes=settings.BUFFER_BEFORE)
    buf_after = timedelta(minutes=settings.BUFFER_AFTER)

    # Окно новой записи
    new_win_start = datetime.combine(appt_date, appt_time_start) - buf_before
    new_win_end = datetime.combine(appt_date, appt_time_end) + buf_after

    query = select(Appointment).where(
        and_(
            Appointment.date == appt_date,
            Appointment.is_cancelled == False,
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
            # Находим ближайшее свободное время
            earliest = (datetime.combine(appt.date, appt.time_end) + buf_after + buf_before)
            return earliest.strftime("%H:%M")
    return None


# --- Auth dependency ---

async def require_auth(request: Request):
    """Проверка авторизации для всех эндпоинтов записей."""
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
    date: date
    time_start: time
    time_end: time
    training_type: Optional[str] = None
    notes: Optional[str] = None
    price: Optional[float] = None
    is_paid: bool = False
    payment_method: Optional[str] = None
    is_confirmed: bool = True


class AppointmentUpdate(BaseModel):
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    date: Optional[date] = None
    time_start: Optional[time] = None
    time_end: Optional[time] = None
    training_type: Optional[str] = None
    notes: Optional[str] = None
    price: Optional[float] = None
    is_paid: Optional[bool] = None
    payment_method: Optional[str] = None
    is_confirmed: Optional[bool] = None
    is_cancelled: Optional[bool] = None


class AppointmentResponse(BaseModel):
    id: int
    client_name: str
    client_phone: Optional[str]
    date: date
    time_start: time
    time_end: time
    training_type: Optional[str]
    notes: Optional[str]
    price: Optional[float]
    is_paid: bool
    payment_method: Optional[str]
    is_confirmed: bool
    is_cancelled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Endpoints ---

@router.get("", response_model=List[AppointmentResponse])
async def get_appointments(
    target_date: Optional[date] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """
    Получить записи.
    - target_date: записи на конкретный день
    - date_from + date_to: записи за диапазон дат
    - без параметров: все записи
    """
    query = select(Appointment).where(Appointment.is_cancelled == False)

    if target_date:
        query = query.where(Appointment.date == target_date)
    elif date_from and date_to:
        query = query.where(and_(Appointment.date >= date_from, Appointment.date <= date_to))

    query = query.order_by(Appointment.date, Appointment.time_start)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    data: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Создать новую запись клиента."""
    # Проверка буфера времени
    conflict_time = await check_buffer_conflict(db, data.date, data.time_start, data.time_end)
    if conflict_time:
        raise HTTPException(
            status_code=409,
            detail=f"Конфликт времени. С учётом перерыва между занятиями ближайшее доступное время: {conflict_time}"
        )
    appointment = Appointment(**data.model_dump())
    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.get("/clients", response_model=List[str])
async def get_client_names(
    q: str = "",
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Автоподсказки имён клиентов для поиска."""
    query = select(Appointment.client_name).distinct()
    if q:
        query = query.where(Appointment.client_name.ilike(f"%{q}%"))
    query = query.order_by(Appointment.client_name).limit(20)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Получить запись по ID."""
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return appointment


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: int,
    data: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Обновить запись."""
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    update_data = data.model_dump(exclude_unset=True)
    
    # Если меняется время — проверяем буфер
    new_date = update_data.get("date", appointment.date)
    new_time_start = update_data.get("time_start", appointment.time_start)
    new_time_end = update_data.get("time_end", appointment.time_end)
    if "date" in update_data or "time_start" in update_data or "time_end" in update_data:
        conflict_time = await check_buffer_conflict(
            db, new_date, new_time_start, new_time_end, exclude_id=appointment_id
        )
        if conflict_time:
            raise HTTPException(
                status_code=409,
                detail=f"Конфликт времени. С учётом перерыва между занятиями ближайшее доступное время: {conflict_time}"
            )

    for key, value in update_data.items():
        setattr(appointment, key, value)

    appointment.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.delete("/{appointment_id}")
async def delete_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Удалить запись (мягкое удаление — отмена)."""
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
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
    _auth: dict = Depends(require_auth),
):
    """Полное удаление записи из БД."""
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    await db.delete(appointment)
    await db.commit()
    return {"success": True, "message": "Запись удалена навсегда"}
