from dataclasses import dataclass
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.models.schedule import (
    TrainerOverrideInterval,
    TrainerSchedule,
    TrainerScheduleOverride,
    TrainerWeeklyInterval,
)


DEFAULT_DURATION_MINUTES = 60
SLOT_STEP_MINUTES = 30
DEFAULT_BOOKING_HORIZON_DAYS = 14
DEFAULT_WEEKLY_INTERVALS = {
    0: ((time(9, 0), time(19, 0)),),
    1: ((time(9, 0), time(19, 0)),),
    2: ((time(9, 0), time(19, 0)),),
    3: ((time(9, 0), time(19, 0)),),
    4: ((time(9, 0), time(19, 0)),),
    5: (),
    6: (),
}


@dataclass(frozen=True)
class EffectiveSchedule:
    duration_minutes: int
    slot_step_minutes: int
    intervals: tuple[tuple[time, time], ...]
    source: str

    @property
    def is_day_off(self) -> bool:
        return not self.intervals


async def get_settings(db: AsyncSession, trainer_id: int) -> tuple[int, int, int, bool]:
    schedule = await db.get(TrainerSchedule, trainer_id)
    if not schedule:
        return (
            DEFAULT_DURATION_MINUTES,
            SLOT_STEP_MINUTES,
            DEFAULT_BOOKING_HORIZON_DAYS,
            True,
        )
    return (
        schedule.duration_minutes,
        schedule.slot_step_minutes,
        schedule.booking_horizon_days,
        False,
    )


async def get_base_intervals(
    db: AsyncSession, trainer_id: int, weekday: int, use_defaults: bool | None = None
) -> tuple[tuple[time, time], ...]:
    if use_defaults is None:
        _, _, _, use_defaults = await get_settings(db, trainer_id)
    if use_defaults:
        return DEFAULT_WEEKLY_INTERVALS[weekday]
    result = await db.execute(
        select(TrainerWeeklyInterval)
        .where(
            TrainerWeeklyInterval.trainer_id == trainer_id,
            TrainerWeeklyInterval.weekday == weekday,
        )
        .order_by(TrainerWeeklyInterval.start_time)
    )
    return tuple((row.start_time, row.end_time) for row in result.scalars().all())


async def get_effective_schedule(
    db: AsyncSession, trainer_id: int, target_date: date
) -> EffectiveSchedule:
    duration, step, _, use_defaults = await get_settings(db, trainer_id)
    override_result = await db.execute(
        select(TrainerScheduleOverride).where(
            TrainerScheduleOverride.trainer_id == trainer_id,
            TrainerScheduleOverride.date == target_date,
        )
    )
    override = override_result.scalar_one_or_none()
    if override:
        if override.is_day_off:
            intervals: tuple[tuple[time, time], ...] = ()
        else:
            interval_result = await db.execute(
                select(TrainerOverrideInterval)
                .where(TrainerOverrideInterval.override_id == override.id)
                .order_by(TrainerOverrideInterval.start_time)
            )
            intervals = tuple(
                (row.start_time, row.end_time) for row in interval_result.scalars().all()
            )
        return EffectiveSchedule(duration, step, intervals, "override")

    intervals = await get_base_intervals(db, trainer_id, target_date.weekday(), use_defaults)
    return EffectiveSchedule(duration, step, intervals, "weekly")


def appointment_fits_intervals(
    start_time: time, end_time: time, intervals: tuple[tuple[time, time], ...]
) -> bool:
    return any(start_time >= interval_start and end_time <= interval_end for interval_start, interval_end in intervals)
