from pydantic import BaseModel, EmailStr
from datetime import date, datetime
from typing import Optional
import uuid

# ── Auth ──────────────────────────────────────────
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "employee"

class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str
    is_active: bool
    model_config = {"from_attributes": True}

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# ── Leaves ────────────────────────────────────────
class LeaveCreate(BaseModel):
    date_from: date
    date_to: date
    type: str              # vacation | day_off | sick
    save_day_off: bool = False

class LeaveUpdate(BaseModel):
    status: str            # approved | rejected

class LeaveOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    date_from: date
    date_to: date
    type: str
    status: str
    save_day_off: bool
    created_at: datetime
    user: Optional[UserOut] = None
    model_config = {"from_attributes": True}

# ── Schedule ──────────────────────────────────────
class SchedulePeriodCreate(BaseModel):
    date_from: date
    date_to: date

class ScheduleOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    shift_date: date
    status: str
    outlook_synced: bool
    user: Optional[UserOut] = None
    model_config = {"from_attributes": True}

class SchedulePeriodOut(BaseModel):
    id: uuid.UUID
    date_from: date
    date_to: date
    status: str
    created_at: datetime
    schedules: list[ScheduleOut] = []
    model_config = {"from_attributes": True}

class ScheduleManualUpdate(BaseModel):
    user_id: uuid.UUID
    shift_date: date