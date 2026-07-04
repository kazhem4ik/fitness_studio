import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для корректных импортов
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from bot_service.core.database import engine, Base
from bot_service.models.users import User
from bot_service.models.bookings import Booking
from bot_service.models.progress import Progress

async def init_models():
    async with engine.begin() as conn:
        print("Создание таблиц в базе данных...")
        # conn.run_sync() позволяет использовать синхронные методы SQLAlchemy (create_all) в асинхронном контексте
        await conn.run_sync(Base.metadata.create_all)
        print("Таблицы успешно созданы!")

if __name__ == "__main__":
    asyncio.run(init_models())
