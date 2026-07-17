import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для корректных импортов
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from sqlalchemy import select
from bot_service.core.database import engine, Base, AsyncSessionLocal
from bot_service.models.users import User
from bot_service.models.bookings import Booking
from bot_service.models.progress import Progress
from bot_service.models.settings import StudioSettings
from bot_service.models.daily_schedule import DailySchedule

async def init_models():
    async with engine.begin() as conn:
        print("Создание таблиц в базе данных...")
        # conn.run_sync() позволяет использовать синхронные методы SQLAlchemy (create_all) в асинхронном контексте
        await conn.run_sync(Base.metadata.create_all)
        print("Таблицы успешно созданы!")
        
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(StudioSettings).where(StudioSettings.id == 1))
        settings_obj = result.scalar_one_or_none()
        if not settings_obj:
            print("Создание базовых настроек...")
            new_settings = StudioSettings(id=1)
            session.add(new_settings)
            await session.commit()
            print("Базовые настройки созданы!")

if __name__ == "__main__":
    asyncio.run(init_models())
