import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import require_manager
from app.core.security import get_password_hash
from app.models.models import User, AuditLog
from app.schemas.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter()



@router.get("/", response_model=list[UserOut])
async def get_users(
    db: AsyncSession = Depends(get_db) 
):
    result = await db.execute(select(User).order_by(User.name))
    return result.scalars().all()


@router.post("/", response_model=UserOut, status_code=201)
async def create_user(
        user_in: UserCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_manager)
):

    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Користувач з таким email вже існує")

    hashed_password = get_password_hash(user_in.password)

    new_user = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=hashed_password,
        role=user_in.role
    )
    db.add(new_user)


    db.add(AuditLog(
        user_id=current_user.id,
        action="👤 Створення користувача",
        details=f"Створено профіль для {user_in.name} ({user_in.email})"
    ))

    await db.commit()
    await db.refresh(new_user)
    return new_user



@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
        user_id: uuid.UUID,
        user_in: UserUpdate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_manager)
):

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")


    update_data = user_in.model_dump(exclude_unset=True)


    if "password" in update_data:
        user.hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]  # Видаляємо сирий пароль зі словника оновлень

    for field, value in update_data.items():
        setattr(user, field, value)


    db.add(AuditLog(
        user_id=current_user.id,
        action="✏️ Оновлення користувача",
        details=f"Оновлено дані для {user.name}"
    ))

    await db.commit()
    await db.refresh(user)

    return user