from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import require_manager
from app.models.models import User, DayOffBalance
from app.schemas.schemas import UserOut

router = APIRouter()

@router.get("/", response_model=list[UserOut])
async def get_users(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_manager)
):
    result = await db.execute(select(User).where(User.is_active == True))
    return result.scalars().all()

@router.get("/{user_id}/balance")
async def get_balance(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_manager)
):
    """Баланс вихідних і чергувань по співробітнику."""
    from datetime import date
    year = date.today().year
    result = await db.execute(
        select(DayOffBalance).where(
            DayOffBalance.user_id == user_id,
            DayOffBalance.year == year
        )
    )
    balance = result.scalar_one_or_none()
    return balance or {"saved_days": 0, "used_days": 0, "total_days": 0}