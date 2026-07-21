import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import secrets

# Вычисляем путь к папке database:
# Локально: .../fitness_studio_mono/database
# В Docker: /database (так как /app/core/config.py -> parent.parent.parent -> / -> /database)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "database" / "planner.db"
DEFAULT_DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

    # JWT Auth
    PLANNER_SECRET_KEY: str = secrets.token_urlsafe(32)
    PLANNER_ADMIN_LOGIN: str = "admin"
    PLANNER_ADMIN_PASSWORD: str = ""  # Set in .env, hashed on first run
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Telegram notifications (placeholder)
    TG_BOT_TOKEN: str = ""
    TG_ADMIN_CHAT_ID: str = ""

    # VAPID keys for Web Push (generate once)
    VAPID_PRIVATE_KEY: str = ""
    VAPID_PUBLIC_KEY: str = ""

    # Буферы времени для записей
    SLOT_DURATION: int = 60      # Длительность тренировки в минутах
    BUFFER_BEFORE: int = 10      # Буфер ДО тренировки (переодевание клиента)
    BUFFER_AFTER: int = 20       # Буфер ПОСЛЕ тренировки (душ и переодевание)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
