import asyncio
from datetime import time  # ДОДАНО
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.models import User, Shift, ShiftType


async def seed():
    async with AsyncSessionLocal() as db:
        # Менеджер
        manager = User(
            name="Олена Менеджер", email="manager@company.com", hashed_password=hash_password("manager123"),
            role="manager",
        )
        # Співробітники
        employees = [
            User(name="Іван Петренко", email="ivan@company.com", hashed_password=hash_password("pass123"),
                 role="employee"),
            User(name="Марія Коваль", email="maria@company.com", hashed_password=hash_password("pass123"),
                 role="employee"),
            User(name="Олег Бойко", email="oleg@company.com", hashed_password=hash_password("pass123"),
                 role="employee"),
            User(name="Тетяна Мороз", email="tanya@company.com", hashed_password=hash_password("pass123"),
                 role="employee"),
            User(name="Дмитро Сидір", email="dmytro@company.com", hashed_password=hash_password("pass123"),
                 role="employee"),
        ]

        # НОВІ ТИПИ ЗМІН З ГОДИНАМИ
        weekday_shift_1 = Shift(name="Будні (Ранок)", shift_type=ShiftType.weekday, duration_hours=3,
                                start_time=time(9, 0))
        weekday_shift_2 = Shift(name="Будні (День)", shift_type=ShiftType.weekday, duration_hours=3,
                                start_time=time(12, 0))
        weekday_shift_3 = Shift(name="Будні (Вечір)", shift_type=ShiftType.weekday, duration_hours=3,
                                start_time=time(15, 0))

        weekend_shift = Shift(name="Вихідний", shift_type=ShiftType.weekend, duration_hours=9, start_time=time(9, 0))

        db.add_all([manager, *employees, weekday_shift_1, weekday_shift_2, weekday_shift_3, weekend_shift])
        await db.commit()
        print("✅ Seed завершено з новими годинами!")


if __name__ == "__main__":
    asyncio.run(seed())