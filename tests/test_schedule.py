import unittest
from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner_service.api.public_booking import get_slots, get_trainers
from planner_service.api.schedule import (
    IntervalInput,
    OverrideUpdate,
    ScheduleUpdate,
    WeeklyDayInput,
    save_exception,
    update_schedule,
)
from planner_service.core.database import Base
from planner_service.core.schedule import get_effective_schedule, get_settings
from planner_service.models import *  # noqa: F401,F403 - register all metadata
from planner_service.models.admin import AdminUser
from planner_service.models.appointment import Appointment
from planner_service.models.client import Client


def next_weekday(target_weekday: int) -> date:
    today = date.today()
    offset = (target_weekday - today.weekday()) % 7
    if offset == 0:
        offset = 7
    return today + timedelta(days=offset)


def weekday_after(minimum_days: int, target_weekday: int = 0) -> date:
    candidate = date.today() + timedelta(days=minimum_days)
    offset = (target_weekday - candidate.weekday()) % 7
    return candidate + timedelta(days=offset)


def default_weekly() -> list[WeeklyDayInput]:
    return [
        WeeklyDayInput(
            weekday=weekday,
            intervals=[IntervalInput(start=time(9), end=time(19))] if weekday < 5 else [],
        )
        for weekday in range(7)
    ]


class ScheduleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with self.session_factory() as session:
            self.admin = AdminUser(
                login="admin-test",
                hashed_password="hash",
                display_name="Администратор",
                role="admin",
                is_active=1,
            )
            self.trainer = AdminUser(
                login="trainer-test",
                hashed_password="hash",
                display_name="Тренер",
                role="trainer",
                is_active=1,
            )
            session.add_all([self.admin, self.trainer])
            await session.commit()
            await session.refresh(self.admin)
            await session.refresh(self.trainer)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_default_schedule_is_weekdays_nine_to_nineteen(self):
        async with self.session_factory() as session:
            monday = next_weekday(0)
            saturday = next_weekday(5)
            monday_schedule = await get_effective_schedule(session, self.trainer.id, monday)
            saturday_schedule = await get_effective_schedule(session, self.trainer.id, saturday)

            self.assertEqual(monday_schedule.duration_minutes, 60)
            self.assertEqual(monday_schedule.slot_step_minutes, 30)
            self.assertEqual(monday_schedule.intervals, ((time(9), time(19)),))
            self.assertTrue(saturday_schedule.is_day_off)

    async def test_public_slots_use_thirty_minute_step_and_block_overlap(self):
        target_date = next_weekday(0)
        async with self.session_factory() as session:
            await update_schedule(
                ScheduleUpdate(weekly=default_weekly()),
                trainer_id=self.trainer.id,
                current_user=self.admin,
                db=session,
            )
            client = Client(full_name="Клиент", trainer_id=self.trainer.id)
            session.add(client)
            await session.flush()
            session.add(
                Appointment(
                    trainer_id=self.trainer.id,
                    client_id=client.id,
                    client_name=client.full_name,
                    date=target_date,
                    time_start=time(9),
                    time_end=time(10),
                )
            )
            await session.commit()

            slots = await get_slots(target_date, self.trainer.id, None, session)
            slot_times = [slot.time for slot in slots]

            self.assertNotIn("09:00", slot_times)
            self.assertNotIn("09:30", slot_times)
            self.assertIn("10:00", slot_times)
            self.assertIn("10:30", slot_times)

    async def test_day_off_requires_confirmation_and_keeps_appointment(self):
        target_date = next_weekday(0)
        async with self.session_factory() as session:
            appointment = Appointment(
                trainer_id=self.trainer.id,
                client_name="Клиент",
                date=target_date,
                time_start=time(11),
                time_end=time(12),
            )
            session.add(appointment)
            await session.commit()

            request = OverrideUpdate(
                start_date=target_date,
                end_date=target_date,
                is_day_off=True,
            )
            first_result = await save_exception(
                request,
                trainer_id=self.trainer.id,
                current_user=self.admin,
                db=session,
            )
            self.assertTrue(first_result["requires_confirmation"])

            request.confirm_conflicts = True
            second_result = await save_exception(
                request,
                trainer_id=self.trainer.id,
                current_user=self.admin,
                db=session,
            )
            self.assertTrue(second_result["saved"])
            self.assertIsNotNone(await session.get(Appointment, appointment.id))
            effective = await get_effective_schedule(session, self.trainer.id, target_date)
            self.assertTrue(effective.is_day_off)

    async def test_trainer_controls_public_booking_horizon(self):
        target_date = weekday_after(20)
        async with self.session_factory() as session:
            result = await update_schedule(
                ScheduleUpdate(
                    duration_minutes=60,
                    booking_horizon_days=45,
                    weekly=default_weekly(),
                ),
                trainer_id=self.trainer.id,
                current_user=self.admin,
                db=session,
            )

            self.assertTrue(result["saved"])
            _, _, horizon, _ = await get_settings(session, self.trainer.id)
            self.assertEqual(horizon, 45)
            trainers = await get_trainers(session)
            self.assertEqual(trainers[0]["booking_horizon_days"], 45)

            available = await get_slots(target_date, self.trainer.id, None, session)
            outside = await get_slots(
                date.today() + timedelta(days=45), self.trainer.id, None, session
            )
            self.assertTrue(available)
            self.assertEqual(outside, [])


if __name__ == "__main__":
    unittest.main()
