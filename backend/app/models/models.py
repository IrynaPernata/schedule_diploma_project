import uuid
from datetime import datetime, date, time
from sqlalchemy import String, Boolean, Integer, Date, Time, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum

class Base(DeclarativeBase):
    pass

class UserRole(str, enum.Enum):
    manager = "manager"
    employee = "employee"

class LeaveType(str, enum.Enum):
    vacation = "vacation"
    day_off = "day_off"
    sick = "sick"

class LeaveStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class ShiftType(str, enum.Enum):
    weekday = "weekday"   # будній день — 3 год
    weekend = "weekend"   # вихідний — 2 особи

class ScheduleStatus(str, enum.Enum):
    planned = "planned"
    confirmed = "confirmed"
    cancelled = "cancelled"

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.employee)
    outlook_user_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    leaves: Mapped[list["Leave"]] = relationship(back_populates="user")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="user")
    day_off_balance: Mapped[list["DayOffBalance"]] = relationship(back_populates="user")

class Leave(Base):
    __tablename__ = "leaves"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    type: Mapped[LeaveType] = mapped_column(Enum(LeaveType))
    status: Mapped[LeaveStatus] = mapped_column(Enum(LeaveStatus), default=LeaveStatus.pending)
    save_day_off: Mapped[bool] = mapped_column(Boolean, default=False)  # зберегти вихідний
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="leaves")

class Shift(Base):
    __tablename__ = "shifts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    shift_type: Mapped[ShiftType] = mapped_column(Enum(ShiftType))
    duration_hours: Mapped[int] = mapped_column(Integer, default=3)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    schedules: Mapped[list["Schedule"]] = relationship(back_populates="shift")

class SchedulePeriod(Base):
    __tablename__ = "schedule_periods"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    schedules: Mapped[list["Schedule"]] = relationship(back_populates="period")

class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    shift_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shifts.id"))
    period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schedule_periods.id"))
    shift_date: Mapped[date] = mapped_column(Date)
    status: Mapped[ScheduleStatus] = mapped_column(Enum(ScheduleStatus), default=ScheduleStatus.planned)
    outlook_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="schedules")
    shift: Mapped["Shift"] = relationship(back_populates="schedules")
    period: Mapped["SchedulePeriod"] = relationship(back_populates="schedules")

class DayOffBalance(Base):
    __tablename__ = "day_off_balance"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    year: Mapped[int] = mapped_column(Integer)
    total_days: Mapped[int] = mapped_column(Integer, default=0)
    used_days: Mapped[int] = mapped_column(Integer, default=0)
    saved_days: Mapped[int] = mapped_column(Integer, default=0)  # перенесені вихідні

    user: Mapped["User"] = relationship(back_populates="day_off_balance")