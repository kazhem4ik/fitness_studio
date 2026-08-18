import unittest
from datetime import date, time

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from planner_service.api.clients import ClientUpdate, update_client
from planner_service.core.database import Base
from planner_service.models import *  # noqa: F401,F403 - register all metadata
from planner_service.models.appointment import Appointment
from planner_service.models.client import Client


class ClientUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_rename_updates_client_and_linked_appointments(self):
        async with self.session_factory() as session:
            client = Client(trainer_id=7, full_name="Старое имя")
            session.add(client)
            await session.flush()
            appointment = Appointment(
                trainer_id=7,
                client_id=client.id,
                client_name="Старое имя",
                date=date.today(),
                time_start=time(10),
                time_end=time(11),
            )
            session.add(appointment)
            await session.commit()

            updated = await update_client(
                client.id,
                ClientUpdate(full_name="Новое имя"),
                db=session,
                auth={"sub": "7"},
            )
            await session.refresh(appointment)

            self.assertEqual(updated.full_name, "Новое имя")
            self.assertEqual(appointment.client_name, "Новое имя")


if __name__ == "__main__":
    unittest.main()
