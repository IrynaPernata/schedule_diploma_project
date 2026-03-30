from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.models import User, Leave, Shift, ShiftType


async def generate_schedule(
        db: AsyncSession, date_from: date, date_to: date, period_id, created_by
) -> list[dict]:
    users_result = await db.execute(select(User).where(User.is_active == True))
    users = users_result.scalars().all()

    leaves_result = await db.execute(
        select(Leave).where(Leave.status == "approved", Leave.date_from <= date_to, Leave.date_to >= date_from)
    )
    unavailable = defaultdict(set)
    for leave in leaves_result.scalars().all():
        current = leave.date_from
        while current <= leave.date_to:
            unavailable[str(leave.user_id)].add(current)
            current += timedelta(days=1)

    # Отримуємо 3 зміни для буднів (відсортовані за часом: 9:00, 12:00, 15:00)
    weekday_shifts_res = await db.execute(
        select(Shift).where(Shift.shift_type == ShiftType.weekday).order_by(Shift.start_time)
    )
    weekday_shifts = weekday_shifts_res.scalars().all()

    # Отримуємо 1 зміну для вихідного
    weekend_shift_res = await db.execute(select(Shift).where(Shift.shift_type == ShiftType.weekend))
    weekend_shift = weekend_shift_res.scalars().first()

    workday_count = defaultdict(int)
    weekend_count = defaultdict(int)
    assignments = []
    current_date = date_from

    while current_date <= date_to:
        is_weekend = current_date.weekday() >= 5
        available = [u for u in users if current_date not in unavailable.get(str(u.id), set())]

        if is_weekend:
            # На вихідні беремо 1 людину з найменшою кількістю вихідних чергувань
            candidates = sorted(available, key=lambda u: weekend_count[str(u.id)])
            if candidates and weekend_shift:
                user = candidates[0]
                assignments.append({
                    "user_id": user.id, "shift_id": weekend_shift.id,
                    "period_id": period_id, "shift_date": current_date
                })
                weekend_count[str(user.id)] += 1
        else:
            # На будні беремо до 3 людей (по кількості доступних змін)
            candidates = sorted(available, key=lambda u: workday_count[str(u.id)])
            chosen = candidates[:len(weekday_shifts)]

            for i, user in enumerate(chosen):
                shift = weekday_shifts[i]
                assignments.append({
                    "user_id": user.id, "shift_id": shift.id,
                    "period_id": period_id, "shift_date": current_date
                })
                workday_count[str(user.id)] += 1

        current_date += timedelta(days=1)

    return assignments