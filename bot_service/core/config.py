from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    TG_BOT_TOKEN: str = ""
    MAX_BOT_TOKEN: str | None = None  # Делаем опциональным на время разработки
    WEBHOOK_HOST: str = ""
    ADMIN_CHAT_ID: str = ""
    STUDIO_OPEN_TIME: str = "10:00"
    STUDIO_CLOSE_TIME: str = "20:00"
    SLOT_DURATION_MIN: int = 75
    LUNCH_START: str = "14:00"
    LUNCH_END: str = "15:00"
    WORK_DAYS: str = "0,1,2,3,4,5"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
