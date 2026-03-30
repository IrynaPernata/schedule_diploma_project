import asyncio
import sys
from app.core.config import settings

# ДІАГНОСТИКА: перевіряємо, чи правильно завантажився .env
print(f"👉 Спроба підключення до: {settings.DATABASE_URL}")

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.database import engine
from app.models.models import Base

async def init_models():
    async with engine.begin() as conn:
        print("Видалення старих таблиць (якщо є)...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Створення нових таблиць...")
        await conn.run_sync(Base.metadata.create_all)
    print("✅ База даних успішно ініціалізована!")

if __name__ == "__main__":
    asyncio.run(init_models())