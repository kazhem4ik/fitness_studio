import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from planner_service.models.admin import AdminUser
from planner_service.core.security import hash_password

async def main():
    engine = create_async_engine("sqlite+aiosqlite:///database/planner.db")
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        user = AdminUser(
            login="Nikita",
            hashed_password=hash_password("1308"),
            display_name="Nikita"
        )
        session.add(user)
        await session.commit()
    print("User Nikita created")

if __name__ == "__main__":
    asyncio.run(main())
