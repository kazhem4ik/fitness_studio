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


async def init_db():
    from planner_service.models.client import Client
    from planner_service.models.package import Package
    from planner_service.models.expense import Expense
    from planner_service.models.income import Income
    from planner_service.models.appointment import Appointment
    from planner_service.models.admin import AdminUser
    
    """Создание всех таблиц."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
