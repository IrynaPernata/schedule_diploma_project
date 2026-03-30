from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import get_current_user, require_manager
from app.models.models import User, Leave, DayOffBalance
from app.schemas.schemas import LeaveCreate, LeaveUpdate, LeaveOut
import uuid

router = APIRouter()

@router.post("/", response_model=LeaveOut, status_code=201)
async def create_leave(
    data: LeaveCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Співробітник подає заявку на відпустку / вихідний."""
    leave = Leave(
        user_id=current_user.id,
        date_from=data.date_from,
        date_to=data.date_to,
        type=data.type,
        save_day_off=data.save_day_off,
        status="pending",
    )
    db.add(leave)
    await db.commit()
    await db.refresh(leave)
    return leave

@router.get("/", response_model=list[LeaveOut])
async def get_leaves(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Менеджер бачить всі заявки, співробітник — лише свої."""
    if current_user.role == "manager":
        result = await db.execute(
            select(Leave).order_by(Leave.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Leave)
            .where(Leave.user_id == current_user.id)
            .order_by(Leave.created_at.desc())
        )
    return result.scalars().all()

@router.patch("/{leave_id}/status", response_model=LeaveOut)
async def update_leave_status(
    leave_id: uuid.UUID,
    data: LeaveUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_manager)   # тільки менеджер
):
    """Менеджер затверджує або відхиляє заявку."""
    result = await db.execute(select(Leave).where(Leave.id == leave_id))
    leave = result.scalar_one_or_none()
    if not leave:
        raise HTTPException(status_code=404, detail="Заявку не знайдено")

    leave.status = data.status

    # Якщо відпустка затверджена і людина хоче зберегти вихідний —
    # додаємо до балансу DayOffBalance
    if data.status == "approved" and leave.save_day_off and leave.type == "day_off":
        year = leave.date_from.year
        balance_result = await db.execute(
            select(DayOffBalance).where(
                DayOffBalance.user_id == leave.user_id,
                DayOffBalance.year == year
            )
        )
        balance = balance_result.scalar_one_or_none()
        if not balance:
            balance = DayOffBalance(user_id=leave.user_id, year=year)
            db.add(balance)
        balance.saved_days += 1

    await db.commit()
    await db.refresh(leave)
    return leave

@router.delete("/{leave_id}", status_code=204)
async def delete_leave(
    leave_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Leave).where(Leave.id == leave_id))
    leave = result.scalar_one_or_none()
    if not leave:
        raise HTTPException(status_code=404, detail="Заявку не знайдено")
    # Видалити може лише власник (якщо pending) або менеджер
    if current_user.role != "manager" and leave.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Немає доступу")
    if current_user.role != "manager" and leave.status != "pending":
        raise HTTPException(status_code=400, detail="Не можна видалити затверджену заявку")

    await db.delete(leave)
    await db.commit()