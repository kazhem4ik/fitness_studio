from datetime import date, timedelta, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.core.database import get_db
from planner_service.core.schedule import (
    DEFAULT_BOOKING_HORIZON_DAYS,
    DEFAULT_DURATION_MINUTES,
    DEFAULT_WEEKLY_INTERVALS,
    SLOT_STEP_MINUTES,
    appointment_fits_intervals,
    get_base_intervals,
    get_settings,
)
from planner_service.core.security import decode_access_token
from planner_service.models.admin import AdminUser
from planner_service.models.appointment import Appointment
from planner_service.models.schedule import (
    TrainerOverrideInterval,
    TrainerSchedule,
    TrainerScheduleOverride,
    TrainerWeeklyInterval,
)


router = APIRouter(prefix="/api/schedule", tags=["schedule"])
COOKIE_NAME = "planner_token"
MAX_OVERRIDE_DAYS = 366
MAX_BOOKING_HORIZON_DAYS = 365


class IntervalInput(BaseModel):
    start: time
    end: time


class WeeklyDayInput(BaseModel):
    weekday: int
    intervals: list[IntervalInput] = Field(default_factory=list)


class ScheduleUpdate(BaseModel):
    duration_minutes: int = DEFAULT_DURATION_MINUTES
    booking_horizon_days: int = DEFAULT_BOOKING_HORIZON_DAYS
    weekly: list[WeeklyDayInput]
    confirm_conflicts: bool = False


class OverrideUpdate(BaseModel):
    start_date: date
    end_date: date
    is_day_off: bool
    intervals: list[IntervalInput] = Field(default_factory=list)
    confirm_conflicts: bool = False


async def require_user(request: Request, db: AsyncSession = Depends(get_db)) -> AdminUser:
    token = request.cookies.get(COOKIE_NAME)
    payload = decode_access_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="Не авторизован")
    user = await db.get(AdminUser, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


async def resolve_trainer(
    requested_trainer_id: Optional[int], current_user: AdminUser, db: AsyncSession
) -> AdminUser:
    if current_user.role == "trainer":
        if requested_trainer_id is not None and requested_trainer_id != current_user.id:
            raise HTTPException(status_code=403, detail="Можно управлять только своим графиком")
        return current_user
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    if requested_trainer_id is None:
        raise HTTPException(status_code=400, detail="Администратору нужно выбрать тренера")
    trainer = await db.get(AdminUser, requested_trainer_id)
    if not trainer or trainer.role != "trainer":
        raise HTTPException(status_code=404, detail="Тренер не найден")
    return trainer


def normalize_intervals(intervals: list[IntervalInput]) -> tuple[tuple[time, time], ...]:
    result = sorted(((item.start, item.end) for item in intervals), key=lambda item: item[0])
    previous_end = None
    for start_time, end_time in result:
        if start_time >= end_time:
            raise HTTPException(status_code=422, detail="Начало интервала должно быть раньше окончания")
        if previous_end is not None and start_time < previous_end:
            raise HTTPException(status_code=422, detail="Рабочие интервалы не должны пересекаться")
        previous_end = end_time
    return tuple(result)


def serialize_intervals(intervals: tuple[tuple[time, time], ...]) -> list[dict]:
    return [
        {"start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")}
        for start, end in intervals
    ]


def serialize_conflicts(appointments: list[Appointment]) -> list[dict]:
    return [
        {
            "id": appointment.id,
            "date": appointment.date.isoformat(),
            "time_start": appointment.time_start.strftime("%H:%M"),
            "time_end": appointment.time_end.strftime("%H:%M"),
            "client_name": appointment.client_name,
        }
        for appointment in appointments
    ]


async def load_schedule_response(db: AsyncSession, trainer: AdminUser) -> dict:
    duration, step, booking_horizon, use_defaults = await get_settings(db, trainer.id)
    weekly = []
    for weekday in range(7):
        intervals = await get_base_intervals(db, trainer.id, weekday, use_defaults)
        weekly.append({"weekday": weekday, "intervals": serialize_intervals(intervals)})
    return {
        "trainer_id": trainer.id,
        "trainer_name": trainer.display_name,
        "duration_minutes": duration,
        "slot_step_minutes": step,
        "booking_horizon_days": booking_horizon,
        "uses_default_schedule": use_defaults,
        "weekly": weekly,
    }


async def future_appointments(
    db: AsyncSession, trainer_id: int, start_date: date, end_date: Optional[date] = None
) -> list[Appointment]:
    query = select(Appointment).where(
        Appointment.trainer_id == trainer_id,
        Appointment.date >= start_date,
        Appointment.is_cancelled == False,
    )
    if end_date is not None:
        query = query.where(Appointment.date <= end_date)
    result = await db.execute(query.order_by(Appointment.date, Appointment.time_start))
    return list(result.scalars().all())


@router.get("")
async def get_schedule(
    trainer_id: Optional[int] = None,
    current_user: AdminUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    trainer = await resolve_trainer(trainer_id, current_user, db)
    return await load_schedule_response(db, trainer)


@router.put("")
async def update_schedule(
    data: ScheduleUpdate,
    trainer_id: Optional[int] = None,
    current_user: AdminUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    trainer = await resolve_trainer(trainer_id, current_user, db)
    if not 15 <= data.duration_minutes <= 240:
        raise HTTPException(status_code=422, detail="Длительность должна быть от 15 до 240 минут")
    if not 1 <= data.booking_horizon_days <= MAX_BOOKING_HORIZON_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"Доступ для записи должен быть от 1 до {MAX_BOOKING_HORIZON_DAYS} дней",
        )
    days = {day.weekday: normalize_intervals(day.intervals) for day in data.weekly}
    if set(days) != set(range(7)) or len(data.weekly) != 7:
        raise HTTPException(status_code=422, detail="Нужно передать каждый день недели один раз")

    override_dates_result = await db.execute(
        select(TrainerScheduleOverride.date).where(
            TrainerScheduleOverride.trainer_id == trainer.id,
            TrainerScheduleOverride.date >= date.today(),
        )
    )
    override_dates = set(override_dates_result.scalars().all())
    appointments = await future_appointments(db, trainer.id, date.today())
    conflicts = [
        appointment
        for appointment in appointments
        if appointment.date not in override_dates
        and not appointment_fits_intervals(
            appointment.time_start, appointment.time_end, days[appointment.date.weekday()]
        )
    ]
    if conflicts and not data.confirm_conflicts:
        return {"saved": False, "requires_confirmation": True, "conflicts": serialize_conflicts(conflicts)}

    schedule = await db.get(TrainerSchedule, trainer.id)
    if schedule is None:
        schedule = TrainerSchedule(trainer_id=trainer.id)
        db.add(schedule)
    schedule.duration_minutes = data.duration_minutes
    schedule.slot_step_minutes = SLOT_STEP_MINUTES
    schedule.booking_horizon_days = data.booking_horizon_days
    await db.execute(
        delete(TrainerWeeklyInterval).where(TrainerWeeklyInterval.trainer_id == trainer.id)
    )
    for weekday, intervals in days.items():
        for start_time, end_time in intervals:
            db.add(
                TrainerWeeklyInterval(
                    trainer_id=trainer.id,
                    weekday=weekday,
                    start_time=start_time,
                    end_time=end_time,
                )
            )
    await db.commit()
    return {"saved": True, "requires_confirmation": False, "schedule": await load_schedule_response(db, trainer)}


@router.get("/exceptions")
async def get_exceptions(
    date_from: date = Query(default_factory=date.today),
    date_to: date = Query(default_factory=lambda: date.today() + timedelta(days=13)),
    trainer_id: Optional[int] = None,
    current_user: AdminUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    trainer = await resolve_trainer(trainer_id, current_user, db)
    result = await db.execute(
        select(TrainerScheduleOverride)
        .where(
            TrainerScheduleOverride.trainer_id == trainer.id,
            TrainerScheduleOverride.date >= date_from,
            TrainerScheduleOverride.date <= date_to,
        )
        .order_by(TrainerScheduleOverride.date)
    )
    response = []
    for override in result.scalars().all():
        intervals_result = await db.execute(
            select(TrainerOverrideInterval)
            .where(TrainerOverrideInterval.override_id == override.id)
            .order_by(TrainerOverrideInterval.start_time)
        )
        intervals = tuple(
            (item.start_time, item.end_time) for item in intervals_result.scalars().all()
        )
        response.append(
            {
                "date": override.date.isoformat(),
                "is_day_off": override.is_day_off,
                "intervals": serialize_intervals(intervals),
            }
        )
    return response


@router.post("/exceptions")
async def save_exception(
    data: OverrideUpdate,
    trainer_id: Optional[int] = None,
    current_user: AdminUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    trainer = await resolve_trainer(trainer_id, current_user, db)
    if data.end_date < data.start_date:
        raise HTTPException(status_code=422, detail="Дата окончания раньше даты начала")
    day_count = (data.end_date - data.start_date).days + 1
    if day_count > MAX_OVERRIDE_DAYS:
        raise HTTPException(status_code=422, detail="Диапазон не может превышать 366 дней")
    intervals = () if data.is_day_off else normalize_intervals(data.intervals)
    if not data.is_day_off and not intervals:
        raise HTTPException(status_code=422, detail="Для рабочего дня нужен хотя бы один интервал")

    appointments = await future_appointments(db, trainer.id, data.start_date, data.end_date)
    conflicts = [
        appointment
        for appointment in appointments
        if data.is_day_off
        or not appointment_fits_intervals(appointment.time_start, appointment.time_end, intervals)
    ]
    if conflicts and not data.confirm_conflicts:
        return {"saved": False, "requires_confirmation": True, "conflicts": serialize_conflicts(conflicts)}

    for offset in range(day_count):
        target_date = data.start_date + timedelta(days=offset)
        result = await db.execute(
            select(TrainerScheduleOverride).where(
                TrainerScheduleOverride.trainer_id == trainer.id,
                TrainerScheduleOverride.date == target_date,
            )
        )
        override = result.scalar_one_or_none()
        if override is None:
            override = TrainerScheduleOverride(trainer_id=trainer.id, date=target_date)
            db.add(override)
            await db.flush()
        override.is_day_off = data.is_day_off
        await db.execute(
            delete(TrainerOverrideInterval).where(
                TrainerOverrideInterval.override_id == override.id
            )
        )
        if not data.is_day_off:
            for start_time, end_time in intervals:
                db.add(
                    TrainerOverrideInterval(
                        override_id=override.id,
                        start_time=start_time,
                        end_time=end_time,
                    )
                )
    await db.commit()
    return {"saved": True, "requires_confirmation": False, "days_updated": day_count}


@router.delete("/exceptions")
async def delete_exceptions(
    start_date: date,
    end_date: date,
    confirm_conflicts: bool = False,
    trainer_id: Optional[int] = None,
    current_user: AdminUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    trainer = await resolve_trainer(trainer_id, current_user, db)
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="Дата окончания раньше даты начала")
    appointments = await future_appointments(db, trainer.id, start_date, end_date)
    _, _, _, use_defaults = await get_settings(db, trainer.id)
    base_by_weekday = {
        weekday: await get_base_intervals(db, trainer.id, weekday, use_defaults)
        for weekday in range(7)
    }
    conflicts = [
        appointment
        for appointment in appointments
        if not appointment_fits_intervals(
            appointment.time_start,
            appointment.time_end,
            base_by_weekday[appointment.date.weekday()],
        )
    ]
    if conflicts and not confirm_conflicts:
        return {"deleted": False, "requires_confirmation": True, "conflicts": serialize_conflicts(conflicts)}

    overrides_result = await db.execute(
        select(TrainerScheduleOverride).where(
            TrainerScheduleOverride.trainer_id == trainer.id,
            TrainerScheduleOverride.date >= start_date,
            TrainerScheduleOverride.date <= end_date,
        )
    )
    overrides = list(overrides_result.scalars().all())
    override_ids = [override.id for override in overrides]
    if override_ids:
        await db.execute(
            delete(TrainerOverrideInterval).where(
                TrainerOverrideInterval.override_id.in_(override_ids)
            )
        )
        await db.execute(
            delete(TrainerScheduleOverride).where(
                TrainerScheduleOverride.id.in_(override_ids)
            )
        )
    await db.commit()
    return {"deleted": True, "requires_confirmation": False, "days_deleted": len(overrides)}
