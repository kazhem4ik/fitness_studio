"""
Скрипт одноразовой миграции для перехода на многопользовательский режим.

Что делает:
  1. Добавляет колонки role, is_active в admin_users
  2. Добавляет trainer_id в appointments, clients, expenses, incomes, push_subscriptions
  3. Создаёт аккаунт 'renata' (role=trainer) если не существует
  4. Привязывает все существующие данные к Renata
  5. Создаёт аккаунт 'admin' (role=admin, пароль=Bond1111)

ВАЖНО: Сделайте резервную копию БД перед запуском!
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from planner_service.core.database import engine
from planner_service.core.security import hash_password


async def migrate():
    async with engine.begin() as conn:
        print("=== Миграция БД: многопользовательский режим ===\n")

        # --- 1. Обновление таблицы admin_users ---
        print("1. Обновление таблицы admin_users...")
        for col_def in [("role", "TEXT DEFAULT 'trainer'"), ("is_active", "INTEGER DEFAULT 1")]:
            col_name, col_type = col_def
            try:
                await conn.execute(text(f"ALTER TABLE admin_users ADD COLUMN {col_name} {col_type}"))
                print(f"   + Добавлена колонка {col_name}")
            except Exception:
                print(f"   ~ Колонка {col_name} уже существует")

        # Обновляем существующего admin на роль admin
        r = await conn.execute(text("UPDATE admin_users SET role='admin', is_active=1 WHERE login='admin'"))
        if r.rowcount:
            print("   ~ Существующий admin: роль обновлена на 'admin'")

        # --- 2. Добавляем trainer_id в таблицы данных ---
        print("\n2. Добавление trainer_id в таблицы...")
        data_tables = ["appointments", "clients", "expenses", "incomes", "push_subscriptions"]
        for table in data_tables:
            try:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN trainer_id INTEGER"))
                print(f"   + {table}: добавлен trainer_id")
            except Exception:
                print(f"   ~ {table}: trainer_id уже существует")

        # --- 3. Создаём/находим аккаунт Renata ---
        print("\n3. Создание/поиск аккаунта Renata...")
        result = await conn.execute(text("SELECT id FROM admin_users WHERE LOWER(login)='renata'"))
        renata_row = result.fetchone()

        if not renata_row:
            temp_pwd = hash_password("renata_change_me")
            await conn.execute(
                text(
                    "INSERT INTO admin_users (login, hashed_password, display_name, role, is_active, created_at)"
                    " VALUES (:login, :pwd, :name, :role, :active, datetime('now'))"
                ),
                {"login": "renata", "pwd": temp_pwd, "name": "Renata", "role": "trainer", "active": 1},
            )
            result = await conn.execute(text("SELECT id FROM admin_users WHERE LOWER(login)='renata'"))
            renata_row = result.fetchone()
            print(f"   + Создан аккаунт renata (id={renata_row[0]})")
            print("   ! ВНИМАНИЕ: временный пароль 'renata_change_me' — смените через панель admin!")
        else:
            await conn.execute(
                text("UPDATE admin_users SET role='trainer', is_active=1 WHERE LOWER(login)='renata'")
            )
            print(f"   ~ Аккаунт renata уже существует (id={renata_row[0]}), роль=trainer")

        renata_id = renata_row[0]

        # --- 4. Привязываем все существующие данные к Renata ---
        print(f"\n4. Привязка данных к Renata (trainer_id={renata_id})...")
        for table in ["appointments", "clients", "expenses", "incomes"]:
            r = await conn.execute(
                text(f"UPDATE {table} SET trainer_id=:tid WHERE trainer_id IS NULL"),
                {"tid": renata_id},
            )
            print(f"   + {table}: обновлено {r.rowcount} записей")

        # --- 5. Создаём аккаунт admin ---
        print("\n5. Создание/обновление аккаунта admin...")
        result = await conn.execute(text("SELECT id FROM admin_users WHERE LOWER(login)='admin'"))
        admin_row = result.fetchone()
        admin_pwd = hash_password("Bond1111")

        if not admin_row:
            await conn.execute(
                text(
                    "INSERT INTO admin_users (login, hashed_password, display_name, role, is_active, created_at)"
                    " VALUES (:login, :pwd, :name, :role, :active, datetime('now'))"
                ),
                {"login": "admin", "pwd": admin_pwd, "name": "Admin", "role": "admin", "active": 1},
            )
            print("   + Создан аккаунт admin (пароль: Bond1111)")
        else:
            await conn.execute(
                text("UPDATE admin_users SET role='admin', is_active=1, hashed_password=:pwd WHERE LOWER(login)='admin'"),
                {"pwd": admin_pwd}
            )
            print("   ~ Аккаунт admin уже существует, роль обновлена на 'admin', пароль сброшен на 'Bond1111'")

        print("\n=== Миграция завершена успешно! ===")
        print("\nЛогины для входа:")
        print("  admin  / Bond1111           (роль: admin  — управление пользователями)")
        print("  renata / <текущий пароль>   (роль: trainer — данные Renata сохранены)")


if __name__ == "__main__":
    asyncio.run(migrate())
