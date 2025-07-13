import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Enum as SQLEnum, String, Text, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base_class import TimestampedBase


class VacancyStatus(str, enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    DRAFT = "draft"


class Vacancy(TimestampedBase):
    title: Mapped[str] = mapped_column(type_=String(255))
    description: Mapped[str] = mapped_column(type_=Text())
    requirements: Mapped[str] = mapped_column(type_=Text())
    salary_min: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), default=None)
    salary_max: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), default=None)
    location: Mapped[str] = mapped_column(type_=String(255))
    position_type: Mapped[str] = mapped_column(type_=String(100))  # player, coach, manager, etc.
    experience_level: Mapped[str] = mapped_column(type_=String(100))  # junior, senior, etc.
    expiry_date: Mapped[datetime] = mapped_column()
    status: Mapped[VacancyStatus] = mapped_column(SQLEnum(VacancyStatus), default=VacancyStatus.DRAFT)
    
    # Foreign Keys
    team_id: Mapped[int] = mapped_column(ForeignKey("user.id"))  # Team user who created this vacancy
    
    # Relationships
    team = relationship("User", back_populates="vacancies")
    applications = relationship("Application", back_populates="vacancy") 