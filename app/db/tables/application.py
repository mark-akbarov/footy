import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Enum as SQLEnum, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base_class import TimestampedBase


class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


class Application(TimestampedBase):
    candidate_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancy.id"))
    status: Mapped[ApplicationStatus] = mapped_column(SQLEnum(ApplicationStatus), default=ApplicationStatus.PENDING)
    cover_letter: Mapped[Optional[str]] = mapped_column(type_=Text(), default=None)
    additional_notes: Mapped[Optional[str]] = mapped_column(type_=Text(), default=None)
    
    # Relationships
    candidate = relationship("User", back_populates="applications")
    vacancy = relationship("Vacancy", back_populates="applications")
    placement = relationship("Placement", back_populates="application", uselist=False) 