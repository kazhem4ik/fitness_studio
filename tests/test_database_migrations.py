import unittest

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from planner_service.core.database import ensure_legacy_columns


class DatabaseMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_columns_are_added_idempotently(self):
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        try:
            async with engine.begin() as connection:
                await connection.execute(text("CREATE TABLE appointments (id INTEGER PRIMARY KEY)"))
                await connection.execute(text("CREATE TABLE clients (id INTEGER PRIMARY KEY)"))
                await connection.execute(
                    text("CREATE TABLE trainer_schedules (trainer_id INTEGER PRIMARY KEY)")
                )

                await ensure_legacy_columns(connection)
                await ensure_legacy_columns(connection)

                appointment_columns = {
                    row[1]
                    for row in (
                        await connection.execute(text("PRAGMA table_info(appointments)"))
                    ).fetchall()
                }
                client_columns = {
                    row[1]
                    for row in (
                        await connection.execute(text("PRAGMA table_info(clients)"))
                    ).fetchall()
                }
                schedule_columns = {
                    row[1]
                    for row in (
                        await connection.execute(text("PRAGMA table_info(trainer_schedules)"))
                    ).fetchall()
                }

            self.assertIn("contact_method", appointment_columns)
            self.assertIn("is_blocked", client_columns)
            self.assertIn("booking_horizon_days", schedule_columns)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    unittest.main()
