from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from planner_service.core.database import Base


class TrainerSchedule(Base):
    __tablename__ = "trainer_schedules"

    trainer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admin_users.id"), primary_key=True
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    slot_step_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    booking_horizon_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class TrainerWeeklyInterval(Base):
    __tablename__ = "trainer_weekly_intervals"
    __table_args__ = (
        UniqueConstraint("trainer_id", "weekday", "start_time", "end_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trainer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admin_users.id"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)


class TrainerScheduleOverride(Base):
    __tablename__ = "trainer_schedule_overrides"
    __table_args__ = (UniqueConstraint("trainer_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trainer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("admin_users.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_day_off: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class TrainerOverrideInterval(Base):
    __tablename__ = "trainer_override_intervals"
    __table_args__ = (
        UniqueConstraint("override_id", "start_time", "end_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    override_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trainer_schedule_overrides.id"), nullable=False, index=True
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
