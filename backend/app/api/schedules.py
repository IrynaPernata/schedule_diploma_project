from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from backend.app.core.database import get_db
from backend.app.core.deps import require_manager, get_current_user
from backend.app.models.models import User, SchedulePeriod, Schedule, Shift
from backend.app.schemas.schemas import SchedulePeriodCreate, SchedulePeriodOut
from backend.app.services.scheduler import generate_schedule
from backend.app.services.outlook import create_outlook_event

router = APIRouter()


@router.post("/generate", response_model=SchedulePeriodOut, status_code=201)
async def create_schedule(
        data: SchedulePeriodCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_manager)
):
    """Генерація нового розкладу на вказаний період (тільки для менеджера)."""
    # 1. Створюємо запис про період
    period = SchedulePeriod(
        date_from=data.date_from,
        date_to=data.date_to,
        created_by=current_user.id
    )
    db.add(period)
    await db.commit()
    await db.refresh(period)

    # 2. Запускаємо алгоритм генерації
    assignments = await generate_schedule(
        db=db,
        date_from=data.date_from,
        date_to=data.date_to,
        period_id=period.id,
        created_by=current_user.id
    )

    if not assignments:
        raise HTTPException(status_code=400,
                            detail="Не вдалося згенерувати розклад. Перевірте наявність співробітників.")

    # 3. Зберігаємо згенеровані зміни в БД
    schedules = [Schedule(**assign) for assign in assignments]
    db.add_all(schedules)
    await db.commit()

    # 4. Динамічна синхронізація з Outlook
    users_res = await db.execute(select(User))
    all_users = {u.id: u for u in users_res.scalars().all()}

    shifts_res = await db.execute(select(Shift))
    all_shifts = {s.id: s for s in shifts_res.scalars().all()}

    for sch in schedules:
        user = all_users.get(sch.user_id)
        shift = all_shifts.get(sch.shift_id)

        if user and shift and shift.start_time:
            # Вираховуємо точну дату і час початку та кінця
            start_dt = datetime.combine(sch.shift_date, shift.start_time)
            end_dt = start_dt + timedelta(hours=shift.duration_hours)

            start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
            end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

            # Відправляємо запит (наразі виводитиме лог, поки немає ключів)
            success = await create_outlook_event(user.email, start_str, end_str)
            if success:
                sch.outlook_synced = True

    await db.commit()  # Зберігаємо статус синхронізації

    # 5. Повертаємо згенерований розклад
    result = await db.execute(
        select(SchedulePeriod)
        .options(
            selectinload(SchedulePeriod.schedules).selectinload(Schedule.user)
        )
        .where(SchedulePeriod.id == period.id)
    )
    return result.scalar_one()


@router.get("/", response_model=list[SchedulePeriodOut])
async def get_periods(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Отримати список всіх згенерованих періодів графіку."""
    result = await db.execute(
        select(SchedulePeriod)
        .options(
            selectinload(SchedulePeriod.schedules).selectinload(Schedule.user)
        )
        .order_by(SchedulePeriod.date_from.desc())
    )
    return result.scalars().all()