from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.deps import get_current_user, require_manager
from app.models.models import User, Leave, DayOffBalance, Schedule, Shift, ShiftType, AuditLog
from app.schemas.schemas import LeaveCreate, LeaveUpdate, LeaveOut
import uuid

router = APIRouter()


@router.post("/", response_model=LeaveOut, status_code=201)
async def create_leave(data: LeaveCreate, db: AsyncSession = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    leave = Leave(user_id=current_user.id, date_from=data.date_from, date_to=data.date_to, type=data.type,
                  save_day_off=data.save_day_off, status="pending")
    db.add(leave)
    await db.commit()
    await db.refresh(leave)
    return leave


@router.get("/", response_model=list[LeaveOut])
async def get_leaves(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Leave).options(selectinload(Leave.user)).order_by(Leave.created_at.desc()))
    return result.scalars().all()


@router.patch("/{leave_id}/status", response_model=LeaveOut)
async def update_leave_status(leave_id: uuid.UUID, data: LeaveUpdate, db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(require_manager)):
    result = await db.execute(select(Leave).options(selectinload(Leave.user)).where(Leave.id == leave_id))
    leave = result.scalar_one_or_none()
    if not leave: raise HTTPException(status_code=404, detail="Заявку не знайдено")

    leave.status = data.status

    if data.status == "approved":
        if leave.type == "day_off":
            year = leave.date_from.year
            balance_result = await db.execute(
                select(DayOffBalance).where(DayOffBalance.user_id == leave.user_id, DayOffBalance.year == year))
            balance = balance_result.scalar_one_or_none()
            if not balance:
                balance = DayOffBalance(user_id=leave.user_id, year=year, saved_days=0, used_days=0)
                db.add(balance)
            balance.used_days += 1
            await db.commit()

        # ЗАПИС В АУДИТ
        type_str = "Відгулу" if leave.type == "day_off" else "Відпустки"
        db.add(AuditLog(user_id=current_user.id, action="✅ Затвердження",
                        details=f"Затвердження {type_str} для {leave.user.name} з {leave.date_from} по {leave.date_to}"))

        conflicts_res = await db.execute(
            select(Schedule).options(selectinload(Schedule.shift)).where(Schedule.user_id == leave.user_id,
                                                                         Schedule.shift_date >= leave.date_from,
                                                                         Schedule.shift_date <= leave.date_to))
        conflicts = conflicts_res.scalars().all()

        if conflicts:
            users_res = await db.execute(select(User).where(User.is_active == True, User.role == "employee"))
            all_users = users_res.scalars().all()

            for sch in conflicts:
                busy_res = await db.execute(select(Schedule.user_id).where(Schedule.shift_date == sch.shift_date))
                busy_users = {row[0] for row in busy_res.fetchall()}

                leaves_res = await db.execute(
                    select(Leave.user_id).where(Leave.status == "approved", Leave.date_from <= sch.shift_date,
                                                Leave.date_to >= sch.shift_date))
                for row in leaves_res.fetchall(): busy_users.add(row[0])

                available = [u for u in all_users if u.id not in busy_users]
                if available:
                    new_user = available[0].id
                    sch.user_id = new_user

                    if sch.shift.shift_type == ShiftType.weekend:
                        year = sch.shift_date.year
                        bal_res = await db.execute(
                            select(DayOffBalance).where(DayOffBalance.user_id == new_user, DayOffBalance.year == year))
                        bal = bal_res.scalar_one_or_none()
                        if not bal:
                            db.add(DayOffBalance(user_id=new_user, year=year, saved_days=1, used_days=0))
                        else:
                            bal.saved_days += 1

                        orig_bal_res = await db.execute(
                            select(DayOffBalance).where(DayOffBalance.user_id == leave.user_id,
                                                        DayOffBalance.year == year))
                        orig_bal = orig_bal_res.scalar_one_or_none()
                        if orig_bal and orig_bal.saved_days > 0:
                            orig_bal.saved_days -= 1
                else:
                    await db.delete(sch)

        await db.commit()
        await db.refresh(leave)

    return leave


@router.delete("/{leave_id}", status_code=204)
async def delete_leave(leave_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Leave).options(selectinload(Leave.user)).where(Leave.id == leave_id))
    leave = result.scalar_one_or_none()
    if not leave: raise HTTPException(status_code=404, detail="Заявку не знайдено")

    if current_user.role != "manager" and leave.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Немає доступу")

    if leave.status == "approved" and leave.type == "day_off":
        year = leave.date_from.year
        balance_res = await db.execute(
            select(DayOffBalance).where(DayOffBalance.user_id == leave.user_id, DayOffBalance.year == year))
        balance = balance_res.scalar_one_or_none()
        if balance and balance.used_days > 0:
            balance.used_days -= 1

    # ЗАПИС В АУДИТ
    db.add(AuditLog(user_id=current_user.id, action="🗑️ Видалення запиту",
                    details=f"Видалено запит працівника {leave.user.name} ({leave.date_from} по {leave.date_to})"))

    await db.delete(leave)
    await db.commit()