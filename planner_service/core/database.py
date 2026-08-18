from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from planner_service.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency для получения сессии БД."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def ensure_legacy_columns(conn):
    """Add columns that create_all cannot add to an existing SQLite database."""
    migrations = (
        (
            "appointments",
            "contact_method",
            "ALTER TABLE appointments ADD COLUMN contact_method VARCHAR",
        ),
        (
            "clients",
            "is_blocked",
            "ALTER TABLE clients ADD COLUMN is_blocked BOOLEAN NOT NULL DEFAULT 0",
        ),
        (
            "trainer_schedules",
            "booking_horizon_days",
            "ALTER TABLE trainer_schedules "
            "ADD COLUMN booking_horizon_days INTEGER NOT NULL DEFAULT 14",
        ),
    )
    for table_name, column_name, statement in migrations:
        columns = {
            row[1]
            for row in (
                await conn.execute(text(f"PRAGMA table_info({table_name})"))
            ).fetchall()
        }
        if column_name not in columns:
            await conn.execute(text(statement))


async def init_db():
    from planner_service.models.client import Client
    from planner_service.models.package import Package
    from planner_service.models.expense import Expense
    from planner_service.models.income import Income
    from planner_service.models.appointment import Appointment
    from planner_service.models.admin import AdminUser
    from planner_service.models.push_subscription import PushSubscription
    from planner_service.models.booking_attempt import BookingAttempt
    from planner_service.models.slot_reservation import SlotReservation
    from planner_service.models.schedule import (
        TrainerSchedule,
        TrainerWeeklyInterval,
        TrainerScheduleOverride,
        TrainerOverrideInterval,
    )

    """Создание всех таблиц."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await ensure_legacy_columns(conn)

