"""
Скрипт для создания админ-пользователя.
Запускать один раз: python -m planner_service.scripts.create_admin
"""
import asyncio
import sys

from sqlalchemy import select

from planner_service.core.database import async_session, init_db
from planner_service.core.security import hash_password
from planner_service.models.admin import AdminUser


async def create_admin():
    await init_db()

    login = input("Введите логин: ").strip()
    password = input("Введите пароль: ").strip()
    display_name = input("Имя для отображения (по умолчанию 'Тренер'): ").strip() or "Тренер"

    if not login or not password:
        print("❌ Логин и пароль обязательны!")
        sys.exit(1)

    async with async_session() as session:
        # Проверяем, нет ли уже такого логина
        result = await session.execute(select(AdminUser).where(AdminUser.login == login))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"⚠️ Пользователь '{login}' уже существует. Обновляем пароль...")
            existing.hashed_password = hash_password(password)
            existing.display_name = display_name
        else:
            admin = AdminUser(
                login=login,
                hashed_password=hash_password(password),
                display_name=display_name,
            )
            session.add(admin)
            print(f"✅ Админ '{login}' создан!")

        await session.commit()
        print("🔐 Готово! Можно входить в систему.")


if __name__ == "__main__":
    asyncio.run(create_admin())
