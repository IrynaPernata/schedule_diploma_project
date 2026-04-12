import asyncio
from datetime import time
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.models import User, Shift, ShiftType

async def seed():
    async with AsyncSessionLocal() as db:
        vova = User(name="Вова (Менеджер)", email="vova@company.com", hashed_password=hash_password("pass123"), role="manager")
        db.add(vova)

        team = [
            {"name": "Іра", "email": "ira@company.com"}, {"name": "Женя", "email": "zhenya@company.com"},
            {"name": "Маша", "email": "masha@company.com"}, {"name": "Даша", "email": "dasha@company.com"},
            {"name": "Юля", "email": "yulia@company.com"}, {"name": "Аня", "email": "anya@company.com"},
        ]
        for person in team:
            db.add(User(name=person["name"], email=person["email"], hashed_password=hash_password("pass123"), role="employee"))

        # НОВІ ЧАСОВІ РАМКИ
        weekday_shift_1 = Shift(name="09:00 - 12:00", shift_type=ShiftType.weekday, duration_hours=3, start_time=time(9, 0))
        weekday_shift_2 = Shift(name="12:00 - 15:00", shift_type=ShiftType.weekday, duration_hours=3, start_time=time(12, 0))
        weekday_shift_3 = Shift(name="15:00 - 18:00", shift_type=ShiftType.weekday, duration_hours=3, start_time=time(15, 0))
        weekend_shift = Shift(name="09:00 - 18:00 (Вихідний)", shift_type=ShiftType.weekend, duration_hours=9, start_time=time(9, 0))

        db.add_all([weekday_shift_1, weekday_shift_2, weekday_shift_3, weekend_shift])
        await db.commit()
        print("✅ Команда додана, нові часові зміни створені!")

if __name__ == "__main__":
    asyncio.run(seed())