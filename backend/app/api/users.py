from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.deps import require_manager
from app.core.security import hash_password
from app.models.models import User, DayOffBalance
from app.schemas.schemas import UserOut, UserCreate  # Переконайся, що UserCreate є в схемах

router = APIRouter()


@router.get("/", response_model=list[UserOut])
async def get_users(db: AsyncSession = Depends(get_db)):
    # Тепер список користувачів доступний всім для вибору при вході
    result = await db.execute(select(User).where(User.is_active == True))
    return result.scalars().all()


@router.post("/", response_model=UserOut)
async def create_new_employee(
        data: UserCreate,
        db: AsyncSession = Depends(get_db),
        _=Depends(require_manager)
):
    """Менеджер додає нового співробітника."""
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Користувач з таким Email вже існує")

    new_user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password("pass123"),  # Пароль за замовчуванням
        role="employee"
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.get("/{user_id}/balance")
async def get_balance(user_id: str, db: AsyncSession = Depends(get_db)):
    from datetime import date
    year = date.today().year
    result = await db.execute(select(DayOffBalance).where(DayOffBalance.user_id == user_id, DayOffBalance.year == year))
    balance = result.scalar_one_or_none()
    return balance or {"saved_days": 0, "used_days": 0}