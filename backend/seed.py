import asyncio
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.models import User, Shift, ShiftType

async def seed():
    async with AsyncSessionLocal() as db:
        # Менеджер
        manager = User(
            name="Олена Менеджер",
            email="manager@company.com",
            hashed_password=hash_password("manager123"),
            role="manager",
        )
        # Співробітники
        employees = [
            User(name="Іван Петренко",  email="ivan@company.com",  hashed_password=hash_password("pass123"), role="employee"),
            User(name="Марія Коваль",   email="maria@company.com", hashed_password=hash_password("pass123"), role="employee"),
            User(name="Олег Бойко",     email="oleg@company.com",  hashed_password=hash_password("pass123"), role="employee"),
            User(name="Тетяна Мороз",   email="tanya@company.com", hashed_password=hash_password("pass123"), role="employee"),
            User(name="Дмитро Сидір",   email="dmytro@company.com",hashed_password=hash_password("pass123"), role="employee"),
        ]

        # Типи змін
        weekday_shift = Shift(
            name="Будній день",
            shift_type=ShiftType.weekday,
            duration_hours=3,
        )
        weekend_shift = Shift(
            name="Вихідний день",
            shift_type=ShiftType.weekend,
            duration_hours=8,
        )

        db.add_all([manager, *employees, weekday_shift, weekend_shift])
        await db.commit()
        print("✅ Seed завершено!")
        print(f"   Менеджер: manager@company.com / manager123")
        print(f"   Співробітники: ivan@company.com / pass123 (та інші)")

asyncio.run(seed())