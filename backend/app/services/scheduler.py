from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import User, Leave, Schedule, Shift, ShiftType

async def generate_schedule(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    period_id,
    created_by
) -> list[dict]:
    """
    Алгоритм генерації графіку:
    - будні: 3-4 чергування на людину по 3 год
    - вихідні: рівно 2 особи
    - враховує відпустки і вихідні
    - балансує навантаження
    """
    # Отримуємо всіх активних співробітників
    users_result = await db.execute(select(User).where(User.is_active == True))
    users = users_result.scalars().all()

    # Отримуємо всі відпустки у діапазоні
    leaves_result = await db.execute(
        select(Leave).where(
            Leave.status == "approved",
            Leave.date_from <= date_to,
            Leave.date_to >= date_from
        )
    )
    leaves = leaves_result.scalars().all()

    # Будуємо множину недоступних дат для кожного user
    unavailable: dict[str, set[date]] = defaultdict(set)
    for leave in leaves:
        current = leave.date_from
        while current <= leave.date_to:
            unavailable[str(leave.user_id)].add(current)
            current += timedelta(days=1)

    # Отримуємо зміни
    weekday_shift = (await db.execute(
        select(Shift).where(Shift.shift_type == ShiftType.weekday)
    )).scalars().first()
    weekend_shift = (await db.execute(
        select(Shift).where(Shift.shift_type == ShiftType.weekend)
    )).scalars().first()

    # Лічильник чергувань для балансу
    workday_count: dict[str, int] = defaultdict(int)
    weekend_count: dict[str, int] = defaultdict(int)

    assignments = []
    current_date = date_from

    while current_date <= date_to:
        is_weekend = current_date.weekday() >= 5  # субота, неділя

        # Доступні на цю дату
        available = [
            u for u in users
            if current_date not in unavailable.get(str(u.id), set())
        ]

        if is_weekend:
            # Вихідний: обираємо 2 з найменшою кількістю вихідних чергувань
            candidates = sorted(available, key=lambda u: weekend_count[str(u.id)])
            chosen = candidates[:2]
            for user in chosen:
                assignments.append({
                    "user_id": user.id,
                    "shift_id": weekend_shift.id if weekend_shift else None,
                    "period_id": period_id,
                    "shift_date": current_date,
                })
                weekend_count[str(user.id)] += 1
        else:
            # Будній: 1 черговий з найменшою кількістю будніх чергувань
            candidates = sorted(available, key=lambda u: workday_count[str(u.id)])
            if candidates:
                user = candidates[0]
                assignments.append({
                    "user_id": user.id,
                    "shift_id": weekday_shift.id if weekday_shift else None,
                    "period_id": period_id,
                    "shift_date": current_date,
                })
                workday_count[str(user.id)] += 1

        current_date += timedelta(days=1)

    return assignments