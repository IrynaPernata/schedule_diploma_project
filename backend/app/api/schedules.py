from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, date
import uuid

from app.core.database import get_db
from app.core.deps import get_current_user, require_manager
from app.models.models import User, SchedulePeriod, Schedule, Shift, ShiftType, DayOffBalance, AuditLog, Leave
from app.services.scheduler import generate_schedule
from app.schemas.schemas import SchedulePeriodCreate, SchedulePeriodOut, SwapRequest, AuditLogOut  # Додано AuditLogOut

router = APIRouter()



@router.get("/audit-logs")
async def get_audit_logs(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_manager)):
    result = await db.execute(
        select(AuditLog).options(selectinload(AuditLog.user)).order_by(AuditLog.created_at.desc()).limit(50))
    return result.scalars().all()


@router.post("/generate", status_code=201)
async def create_schedule(db: AsyncSession = Depends(get_db), current_user: User = Depends(require_manager)):
    date_from = date.today()
    date_to = date_from + timedelta(days=30)


    old_schedules_res = await db.execute(
        select(Schedule).options(selectinload(Schedule.shift)).where(Schedule.shift_date >= date_from))
    for sch in old_schedules_res.scalars().all():
        if sch.shift and sch.shift.shift_type == ShiftType.weekend:
            bal_res = await db.execute(select(DayOffBalance).where(DayOffBalance.user_id == sch.user_id,
                                                                   DayOffBalance.year == sch.shift_date.year))
            bal = bal_res.scalar_one_or_none()
            if bal and bal.saved_days > 0: bal.saved_days -= 1
        await db.delete(sch)
    await db.commit()

    await db.execute(delete(SchedulePeriod).where(SchedulePeriod.date_from >= date_from))
    await db.commit()


    period = SchedulePeriod(date_from=date_from, date_to=date_to, created_by=current_user.id)
    db.add(period)
    await db.commit()
    await db.refresh(period)

    assignments = await generate_schedule(db, date_from, date_to, period.id, current_user.id)
    if not assignments: raise HTTPException(status_code=400, detail="Немає доступних співробітників.")

    schedules = [Schedule(**assign) for assign in assignments]
    db.add_all(schedules)


    db.add(AuditLog(user_id=current_user.id, action="🔄 Генерація розкладу",
                    details=f"Згенеровано новий графік з {date_from} по {date_to}"))
    await db.commit()

    from app.services.outlook import create_outlook_event

    shifts_res = await db.execute(select(Shift))
    all_shifts = {s.id: s for s in shifts_res.scalars().all()}
    users_res = await db.execute(select(User))
    all_users = {u.id: u for u in users_res.scalars().all()}

    local_bals = {}
    for sch in schedules:
        user = all_users.get(sch.user_id)
        shift = all_shifts.get(sch.shift_id)

        # Оновлення балансу за вихідні
        if shift and shift.shift_type == ShiftType.weekend:
            year = sch.shift_date.year
            key = f"{sch.user_id}_{year}"
            if key not in local_bals:
                bal_res = await db.execute(
                    select(DayOffBalance).where(DayOffBalance.user_id == sch.user_id, DayOffBalance.year == year))
                bal = bal_res.scalar_one_or_none()
                if not bal:
                    bal = DayOffBalance(user_id=sch.user_id, year=year, saved_days=0, used_days=0)
                    db.add(bal)
                local_bals[key] = bal
            local_bals[key].saved_days += 1


        if user and shift and shift.start_time:
            start_dt = datetime.combine(sch.shift_date, shift.start_time)
            end_dt = start_dt + timedelta(hours=shift.duration_hours)
            success = await create_outlook_event(
                user.email,
                start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                end_dt.strftime("%Y-%m-%dT%H:%M:%S")
            )
            if success: sch.outlook_synced = True

    await db.commit()

    result = await db.execute(select(SchedulePeriod).options(
        selectinload(SchedulePeriod.schedules).selectinload(Schedule.user),
        selectinload(SchedulePeriod.schedules).selectinload(Schedule.shift)
    ).where(SchedulePeriod.id == period.id))
    return result.scalar_one()


@router.get("/")
async def get_periods(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SchedulePeriod).options(selectinload(SchedulePeriod.schedules).selectinload(Schedule.user),
                                       selectinload(SchedulePeriod.schedules).selectinload(Schedule.shift)).order_by(
            SchedulePeriod.date_from.desc()))
    return result.scalars().all()


# backend/app/api/schedules.py

@router.get("/export/me", response_class=PlainTextResponse)
async def export_my_schedule_ics(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 1. Завантажуємо чергування працівника
    sched_result = await db.execute(
        select(Schedule).options(selectinload(Schedule.shift))
        .where(Schedule.user_id == current_user.id, Schedule.shift_date >= date.today())
    )
    schedules = sched_result.scalars().all()

    # 2. Завантажуємо затверджені відпустки та відгули працівника
    leaves_result = await db.execute(
        select(Leave).where(Leave.user_id == current_user.id, Leave.status == "approved", Leave.date_to >= date.today())
    )
    leaves = leaves_result.scalars().all()

    ics_content = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Shift Scheduler//UA",
        "METHOD:PUBLISH"
    ]

    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for sch in schedules:
        if not sch.shift or not sch.shift.start_time: continue
        start_dt = datetime.combine(sch.shift_date, sch.shift.start_time)
        end_dt = start_dt + timedelta(hours=sch.shift.duration_hours)

        dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
        dtend = end_dt.strftime("%Y%m%dT%H%M%S")

        ics_content.extend([
            "BEGIN:VEVENT",
            f"UID:shift-{sch.id}@shiftscheduler.local",
            f"DTSTAMP:{now}",
            f"DTSTART;TZID=Europe/Kyiv:{dtstart}",
            f"DTEND;TZID=Europe/Kyiv:{dtend}",
            f"SUMMARY:📌 Чергування: {sch.shift.name}",
            f"DESCRIPTION:Тривалість: {sch.shift.duration_hours} год",
            "PRIORITY:5",
            "END:VEVENT"
        ])


    for l in leaves:

        start_str = l.date_from.strftime("%Y%m%d")
        end_str = (l.date_to + timedelta(days=1)).strftime("%Y%m%d")

        summary = "🌴 Відпустка" if l.type == "vacation" else "🏠 Відгул"

        ics_content.extend([
            "BEGIN:VEVENT",
            f"UID:leave-{l.id}@shiftscheduler.local",
            f"DTSTAMP:{now}",
            f"DTSTART;VALUE=DATE:{start_str}",
            f"DTEND;VALUE=DATE:{end_str}",
            f"SUMMARY:{summary}",
            "X-MICROSOFT-CDO-BUSYSTATUS:OOF",
            "TRANSP:TRANSPARENT",
            "END:VEVENT"
        ])

    ics_content.append("END:VCALENDAR")


    safe_name = current_user.email.split('@')[0]
    filename = f"schedule_{safe_name}.ics"
    return PlainTextResponse(
        "\n".join(ics_content),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
        media_type="text/calendar"
    )


@router.post("/swap", status_code=200)
async def swap_schedules(data: SwapRequest, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    sch1 = await db.get(Schedule, data.schedule_id_1,
                        options=[selectinload(Schedule.user), selectinload(Schedule.shift)])
    sch2 = await db.get(Schedule, data.schedule_id_2,
                        options=[selectinload(Schedule.user), selectinload(Schedule.shift)])

    if not sch1 or not sch2: raise HTTPException(status_code=404, detail="Чергування не знайдено")
    if sch1.shift.shift_type != sch2.shift.shift_type: raise HTTPException(status_code=400,
                                                                           detail="Заборонено! Можна міняти лише будні на будні, а вихідні на вихідні.")

    existing_1 = await db.execute(
        select(Schedule).where(Schedule.user_id == sch1.user_id, Schedule.shift_date == sch2.shift_date,
                               Schedule.id != sch2.id))
    if existing_1.scalar_one_or_none(): raise HTTPException(status_code=400, detail="Заборонено 2 зміни в день!")
    existing_2 = await db.execute(
        select(Schedule).where(Schedule.user_id == sch2.user_id, Schedule.shift_date == sch1.shift_date,
                               Schedule.id != sch1.id))
    if existing_2.scalar_one_or_none(): raise HTTPException(status_code=400, detail="Заборонено 2 зміни в день!")

    old_user_1 = sch1.user_id
    old_user_2 = sch2.user_id

    sch1.user_id = old_user_2
    sch2.user_id = old_user_1


    log = AuditLog(user_id=current_user.id, action="🔀 Обмін змінами",
                   details=f"Поміняно місцями: {sch1.user.name} ({sch1.shift_date}) та {sch2.user.name} ({sch2.shift_date})")
    db.add(log)

    await db.commit()

    if sch1.shift.shift_type == ShiftType.weekend:
        async def rebalance_weekdays(target_date, user_gaining_weekend, user_losing_weekend):
            week_start = target_date - timedelta(days=target_date.weekday())
            week_end = week_start + timedelta(days=4)
            shifts_res = await db.execute(
                select(Schedule).join(Shift).where(
                    and_(Schedule.user_id == user_gaining_weekend, Schedule.shift_date >= week_start,
                         Schedule.shift_date <= week_end, Shift.shift_type == ShiftType.weekday))
            )
            shifts_to_give = shifts_res.scalars().all()
            for s_to_give in shifts_to_give:
                conflict = await db.execute(select(Schedule).where(Schedule.user_id == user_losing_weekend,
                                                                   Schedule.shift_date == s_to_give.shift_date))
                if not conflict.scalar_one_or_none():
                    s_to_give.user_id = user_losing_weekend
                    db.add(s_to_give)
                    await db.commit()
                    return True

        await rebalance_weekdays(sch1.shift_date, user_gaining_weekend=old_user_2, user_losing_weekend=old_user_1)
        await rebalance_weekdays(sch2.shift_date, user_gaining_weekend=old_user_1, user_losing_weekend=old_user_2)

    return {"status": "success"}