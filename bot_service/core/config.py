from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    TG_BOT_TOKEN: str = ""
    MAX_BOT_TOKEN: str | None = None  # Делаем опциональным на время разработки
    WEBHOOK_HOST: str = ""
    ADMIN_CHAT_ID: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
