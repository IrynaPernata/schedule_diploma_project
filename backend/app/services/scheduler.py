from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.models import User, Leave, Shift, ShiftType, Schedule, SchedulePeriod, DayOffBalance


async def generate_schedule(db: AsyncSession, date_from: date, date_to: date, period_id, created_by) -> list[dict]:
    users_result = await db.execute(select(User).where(User.is_active == True, User.role == "employee"))
    users = users_result.scalars().all()

    leaves_result = await db.execute(
        select(Leave).where(Leave.status == "approved", Leave.date_from <= date_to, Leave.date_to >= date_from))
    unavailable = defaultdict(set)
    for leave in leaves_result.scalars().all():
        curr = leave.date_from
        while curr <= leave.date_to:
            unavailable[str(leave.user_id)].add(curr)
            curr += timedelta(days=1)

    weekday_shifts_res = await db.execute(
        select(Shift).where(Shift.shift_type == ShiftType.weekday).order_by(Shift.start_time))
    weekday_shifts = weekday_shifts_res.scalars().all()
    weekend_shift_res = await db.execute(select(Shift).where(Shift.shift_type == ShiftType.weekend))
    weekend_shift = weekend_shift_res.scalars().first()

    past_schedules_res = await db.execute(
        select(Schedule).options(selectinload(Schedule.shift)).where(Schedule.shift_date < date_from).order_by(
            Schedule.shift_date.asc()))
    past_schedules = past_schedules_res.scalars().all()

    last_weekend_date = defaultdict(lambda: date(2000, 1, 1))
    last_weekend_day = defaultdict(int)
    weekend_count = defaultdict(int)
    last_shift_id = defaultdict(str)
    total_weekday_shifts = defaultdict(int)

    for sch in past_schedules:
        if sch.shift and sch.shift.shift_type == ShiftType.weekend:
            last_weekend_date[str(sch.user_id)] = sch.shift_date
            last_weekend_day[str(sch.user_id)] = sch.shift_date.weekday()
            weekend_count[str(sch.user_id)] += 1
        elif sch.shift and sch.shift.shift_type == ShiftType.weekday:
            total_weekday_shifts[str(sch.user_id)] += 1
            last_shift_id[str(sch.user_id)] = str(sch.shift_id)

    assignments = []
    works_weekend_this_week = defaultdict(bool)

    current_date = date_from
    while current_date <= date_to:
        if current_date.weekday() >= 5:
            week_num = current_date.isocalendar()[1]
            today_weekday = current_date.weekday()
            available = [u for u in users if current_date not in unavailable.get(str(u.id), set())]

            def weekend_key(u):
                days_since = (current_date - last_weekend_date[str(u.id)]).days
                same_day_penalty = 1 if last_weekend_day[str(u.id)] == today_weekday else 0

                # НОВА ЛОГІКА: Захист від перепрацювань.
                # Якщо пройшло менше 18 днів (менше 3 тижнів), ставимо жорсткий блок.
                too_soon_penalty = 1 if days_since < 18 else 0

                return (
                    weekend_count[str(u.id)],  # 1. Загальна кількість (порівну)
                    too_soon_penalty,  # 2. Не ставити занадто швидко!
                    same_day_penalty,  # 3. Бажано міняти дні (якщо дозволяє час)
                    -days_since  # 4. Хто найдовше відпочивав
                )

            candidates = sorted(available, key=weekend_key)
            if candidates and weekend_shift:
                user = candidates[0]
                assignments.append({"user_id": user.id, "shift_id": weekend_shift.id, "period_id": period_id,
                                    "shift_date": current_date})
                last_weekend_date[str(user.id)] = current_date
                last_weekend_day[str(user.id)] = today_weekday
                weekend_count[str(user.id)] += 1
                works_weekend_this_week[f"{user.id}_{week_num}"] = True
        current_date += timedelta(days=1)

    current_date = date_from
    current_week = -1
    weekday_shifts_this_week = defaultdict(int)

    while current_date <= date_to:
        week_num = current_date.isocalendar()[1]
        if week_num != current_week:
            current_week = week_num
            weekday_shifts_this_week.clear()

        if current_date.weekday() < 5:
            available = [u for u in users if current_date not in unavailable.get(str(u.id), set())]
            current_available = available.copy()

            for shift in weekday_shifts:
                if not current_available: break

                def weekday_key(u):
                    is_weekend = works_weekend_this_week[f"{u.id}_{week_num}"]
                    same_shift_penalty = 1 if last_shift_id[str(u.id)] == str(shift.id) else 0
                    return (weekday_shifts_this_week[str(u.id)], is_weekend, total_weekday_shifts[str(u.id)],
                            same_shift_penalty)

                candidates = sorted(current_available, key=weekday_key)
                if candidates:
                    user = candidates[0]
                    assignments.append(
                        {"user_id": user.id, "shift_id": shift.id, "period_id": period_id, "shift_date": current_date})
                    weekday_shifts_this_week[str(user.id)] += 1
                    total_weekday_shifts[str(user.id)] += 1
                    last_shift_id[str(user.id)] = str(shift.id)
                    current_available.remove(user)
        current_date += timedelta(days=1)
    return assignments


async def regenerate_future(db: AsyncSession, start_date: date):
    period_res = await db.execute(
        select(SchedulePeriod).where(SchedulePeriod.date_to >= start_date).order_by(SchedulePeriod.date_from.asc()))
    period = period_res.scalars().first()
    if not period: return

    regen_start = max(start_date, period.date_from)
    regen_end = period.date_to

    try:
        old_schedules_res = await db.execute(
            select(Schedule).options(selectinload(Schedule.shift)).where(Schedule.shift_date >= regen_start,
                                                                         Schedule.shift_date <= regen_end))
        for sch in old_schedules_res.scalars().all():
            if sch.shift and sch.shift.shift_type == ShiftType.weekend:
                year = sch.shift_date.year
                bal_res = await db.execute(
                    select(DayOffBalance).where(DayOffBalance.user_id == sch.user_id, DayOffBalance.year == year))
                bal = bal_res.scalar_one_or_none()
                if bal and bal.saved_days > 0: bal.saved_days -= 1
            await db.delete(sch)

        new_assignments = await generate_schedule(db, regen_start, regen_end, period.id, period.created_by)
        if new_assignments:
            schedules = [Schedule(**a) for a in new_assignments]
            db.add_all(schedules)

            shifts_res = await db.execute(select(Shift))
            all_shifts = {s.id: s for s in shifts_res.scalars().all()}

            local_bals = {}
            for sch in schedules:
                shift = all_shifts.get(sch.shift_id)
                if shift and shift.shift_type == ShiftType.weekend:
                    year = sch.shift_date.year
                    key = f"{sch.user_id}_{year}"
                    if key not in local_bals:
                        bal_res = await db.execute(select(DayOffBalance).where(DayOffBalance.user_id == sch.user_id,
                                                                               DayOffBalance.year == year))
                        bal = bal_res.scalar_one_or_none()
                        if not bal:
                            bal = DayOffBalance(user_id=sch.user_id, year=year, saved_days=0, used_days=0)
                            db.add(bal)
                        local_bals[key] = bal
                    local_bals[key].saved_days += 1

        await db.commit()
    except Exception as e:
        await db.rollback()
        print("Помилка генерації:", str(e))