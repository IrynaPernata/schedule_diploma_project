from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import require_manager, get_current_user
from app.models.models import User, SchedulePeriod, Schedule
from app.schemas.schemas import SchedulePeriodCreate, SchedulePeriodOut
from app.services.scheduler import generate_schedule
import uuid

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
        raise HTTPException(status_code=400, detail="Не вдалося згенерувати розклад. Перевірте наявність співробітників.")

    # 3. Зберігаємо згенеровані зміни в БД
    schedules = [Schedule(**assign) for assign in assignments]
    db.add_all(schedules)
    await db.commit()

    # 4. Повертаємо період разом зі змінами та користувачами (використовуємо selectinload для асинхронності)
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