import re
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.core.database import get_db
from planner_service.core.config import settings
from planner_service.models.client import Client
from planner_service.models.appointment import Appointment
from planner_service.models.admin import AdminUser
from planner_service.models.booking_attempt import BookingAttempt
from planner_service.models.slot_reservation import SlotReservation
from planner_service.core.push import send_push_notification

router = APIRouter(tags=["Public Booking"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SlotResponse(BaseModel):
    time: str
    available: bool


class BookingRequest(BaseModel):
    date: str
    time: str
    client_name: str
    client_phone: str
    trainer_id: int
    # Honeypot: живой пользователь не видит это поле и не заполняет
    website: Optional[str] = None
    # Идентификатор вкладки для привязки резервации
    session_id: Optional[str] = None


class ReserveRequest(BaseModel):
    trainer_id: int
    date: str
    time: str
    session_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    if len(digits) == 11 and digits.startswith("7"):
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
    return phone


def get_client_ip(request: Request) -> str:
    """Получить реальный IP клиента.

    Nginx выставляет X-Real-IP = $remote_addr — этот заголовок
    нельзя подделать из тела запроса, он проставляется только Nginx'ом.
    Fallback на request.client.host для локального запуска без Nginx.
    """
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


async def _purge_expired_reservations(db: AsyncSession) -> None:
    """Удалить просроченные резервации (паттерн «очистка при чтении»)."""
    now = datetime.utcnow()
    await db.execute(
        delete(SlotReservation).where(SlotReservation.expires_at < now)
    )


async def _purge_old_attempts(db: AsyncSession) -> None:
    """Удалить устаревшие попытки (старше максимального из двух окон)."""
    max_window = max(
        settings.RATE_LIMIT_IP_WINDOW_SECONDS,
        settings.RATE_LIMIT_PHONE_WINDOW_SECONDS,
    )
    cutoff = datetime.utcnow() - timedelta(seconds=max_window)
    await db.execute(
        delete(BookingAttempt).where(BookingAttempt.created_at < cutoff)
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

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
async def get_slots(
    d: date,
    trainer_id: int,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Свободные слоты на дату для конкретного тренера.

    Учитывает временные резервации:
    - Слот, удерживаемый другой сессией, отображается как недоступный.
    - Слот, удерживаемый текущей сессией, остаётся доступным для неё же.
    """
    # Очищаем просроченные резервации при каждом запросе слотов
    await _purge_expired_reservations(db)
    await db.commit()

    open_hour, open_minute = map(int, settings.STUDIO_OPEN_TIME.split(':'))
    close_hour, close_minute = map(int, settings.STUDIO_CLOSE_TIME.split(':'))

    start_time = datetime(d.year, d.month, d.day, open_hour, open_minute)
    end_time = datetime(d.year, d.month, d.day, close_hour, close_minute)

    # Подтверждённые записи
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

    # Активные резервации (чужие — для текущей сессии слот остаётся доступным)
    res_result = await db.execute(
        select(SlotReservation).where(
            SlotReservation.trainer_id == trainer_id,
            SlotReservation.date == d,
        )
    )
    reservations = res_result.scalars().all()

    # Множество зарезервированных времён другими сессиями
    reserved_by_others = set()
    for rsv in reservations:
        if rsv.session_id != session_id:
            reserved_by_others.add((rsv.time_start.hour, rsv.time_start.minute))

    slots = []
    current_time = start_time
    while current_time + timedelta(minutes=settings.SLOT_DURATION) <= end_time:
        slot_end = current_time + timedelta(minutes=settings.SLOT_DURATION)
        available = True

        # Проверка подтверждённых записей
        for (occ_start, occ_end) in occupied_times:
            if current_time < occ_end and slot_end > occ_start:
                available = False
                break

        # Прошедшее время
        if current_time < datetime.now() + timedelta(hours=1):
            available = False

        # Чужая резервация
        if available and (current_time.hour, current_time.minute) in reserved_by_others:
            available = False

        if available:
            slots.append(SlotResponse(time=current_time.strftime("%H:%M"), available=True))

        current_time += timedelta(minutes=settings.SLOT_DURATION)

    return slots


@router.post("/slots/reserve")
async def reserve_slot(req: ReserveRequest, db: AsyncSession = Depends(get_db)):
    """Временно зарезервировать слот при выборе времени (до отправки формы).

    Один session_id — одна активная резервация. При смене слота —
    существующая запись обновляется (upsert).
    """
    # Очищаем просроченные резервации
    await _purge_expired_reservations(db)

    try:
        slot_date = datetime.strptime(req.date, "%Y-%m-%d").date()
        slot_time = datetime.strptime(req.time, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты или времени")

    # Проверяем, нет ли подтверждённой записи на этот слот
    slot_end_dt = datetime.combine(slot_date, slot_time) + timedelta(minutes=settings.SLOT_DURATION)
    slot_end_time = slot_end_dt.time()

    conflict = await db.execute(
        select(Appointment).join(Client, Appointment.client_id == Client.id).where(
            Appointment.date == slot_date,
            Appointment.trainer_id == req.trainer_id,
            Appointment.time_start < slot_end_time,
            Appointment.time_end > slot_time,
            Appointment.is_cancelled == False,
            Client.deleted_at.is_(None)
        )
    )
    if conflict.scalars().first():
        return {"ok": False, "reason": "К сожалению, это время уже занято"}

    # Проверяем, нет ли активной резервации другой сессии на этот слот
    other_rsv = await db.execute(
        select(SlotReservation).where(
            SlotReservation.trainer_id == req.trainer_id,
            SlotReservation.date == slot_date,
            SlotReservation.time_start == slot_time,
            SlotReservation.session_id != req.session_id,
        )
    )
    if other_rsv.scalars().first():
        return {"ok": False, "reason": "Этот слот только что зарезервировал другой пользователь"}

    # Upsert: обновляем существующую резервацию или создаём новую
    expires_at = datetime.utcnow() + timedelta(minutes=settings.SLOT_RESERVATION_MINUTES)

    existing = await db.execute(
        select(SlotReservation).where(SlotReservation.session_id == req.session_id)
    )
    rsv = existing.scalars().first()

    if rsv:
        rsv.trainer_id = req.trainer_id
        rsv.date = slot_date
        rsv.time_start = slot_time
        rsv.expires_at = expires_at
    else:
        rsv = SlotReservation(
            trainer_id=req.trainer_id,
            date=slot_date,
            time_start=slot_time,
            session_id=req.session_id,
            expires_at=expires_at,
        )
        db.add(rsv)

    await db.commit()
    return {"ok": True}


@router.post("/book")
async def create_booking(
    req: BookingRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Записать клиента к конкретному тренеру.

    Порядок проверок защиты:
    1. Honeypot      — тихий успех без создания записи
    2. Blacklist     — 429 (нейтральное сообщение)
    3. Rate Limiting — 429 по IP и по телефону
    4. Conflict      — 400 занятое время
    """
    # ------------------------------------------------------------------
    # 1. Honeypot: если поле заполнено — имитируем успех без записи в БД
    # ------------------------------------------------------------------
    if req.website:
        return {"status": "ok", "message": "Вы успешно записаны!", "client_id": 0}

    # ------------------------------------------------------------------
    # 2. Форматирование телефона
    # ------------------------------------------------------------------
    formatted_phone = format_phone(req.client_phone)
    if not formatted_phone:
        raise HTTPException(status_code=400, detail="Неверный формат телефона")

    # ------------------------------------------------------------------
    # 3. Blacklist: проверяем, заблокирован ли номер у этого тренера
    # ------------------------------------------------------------------
    blocked_check = await db.execute(
        select(Client).where(
            Client.phone == formatted_phone,
            Client.trainer_id == req.trainer_id,
            Client.is_blocked == True,
        )
    )
    if blocked_check.scalars().first():
        raise HTTPException(
            status_code=429,
            detail="Слишком много попыток записи, попробуйте позже"
        )

    # ------------------------------------------------------------------
    # 4. Rate Limiting
    # ------------------------------------------------------------------
    client_ip = get_client_ip(request)
    now = datetime.utcnow()

    # Очищаем устаревшие попытки перед проверкой
    await _purge_old_attempts(db)

    # Лимит по IP
    ip_window_start = now - timedelta(seconds=settings.RATE_LIMIT_IP_WINDOW_SECONDS)
    ip_count_res = await db.execute(
        select(func.count(BookingAttempt.id)).where(
            BookingAttempt.ip_address == client_ip,
            BookingAttempt.created_at >= ip_window_start,
        )
    )
    ip_count = ip_count_res.scalar_one()
    if ip_count >= settings.RATE_LIMIT_IP_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Слишком много попыток записи, попробуйте позже"
        )

    # Лимит по телефону
    phone_window_start = now - timedelta(seconds=settings.RATE_LIMIT_PHONE_WINDOW_SECONDS)
    phone_count_res = await db.execute(
        select(func.count(BookingAttempt.id)).where(
            BookingAttempt.phone == formatted_phone,
            BookingAttempt.created_at >= phone_window_start,
        )
    )
    phone_count = phone_count_res.scalar_one()
    if phone_count >= settings.RATE_LIMIT_PHONE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Слишком много попыток записи, попробуйте позже"
        )

    # Записываем попытку (до создания записи, чтобы учитывать все запросы)
    attempt = BookingAttempt(ip_address=client_ip, phone=formatted_phone)
    db.add(attempt)
    await db.flush()

    # ------------------------------------------------------------------
    # 5. Проверка тренера
    # ------------------------------------------------------------------
    trainer_res = await db.execute(
        select(AdminUser).where(AdminUser.id == req.trainer_id, AdminUser.is_active == 1)
    )
    trainer = trainer_res.scalar_one_or_none()
    if not trainer:
        raise HTTPException(status_code=404, detail="Тренер не найден")

    # ------------------------------------------------------------------
    # 6. Поиск / создание клиента
    # ------------------------------------------------------------------
    result = await db.execute(
        select(Client).where(
            Client.phone == formatted_phone,
            Client.trainer_id == req.trainer_id
        )
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
        client.full_name = req.client_name
        await db.flush()
        is_new = True

    # ------------------------------------------------------------------
    # 7. Разбор даты/времени и проверка конфликта
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 8. Снимаем временную резервацию этой сессии (если была)
    # ------------------------------------------------------------------
    if req.session_id:
        await db.execute(
            delete(SlotReservation).where(
                SlotReservation.session_id == req.session_id
            )
        )

    # ------------------------------------------------------------------
    # 9. Создаём запись
    # ------------------------------------------------------------------
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
