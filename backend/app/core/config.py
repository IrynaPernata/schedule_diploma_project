from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Значення за замовчуванням (якщо .env не знайдено)
    DATABASE_URL: str = "postgresql+asyncpg://shift_user:shift_pass@127.0.0.1:5433/shift_scheduler"
    SECRET_KEY: str = "super-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Ключі для Outlook
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_TENANT_ID: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ігнорувати зайві змінні з середовища

settings = Settings()