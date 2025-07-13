import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Enum as SQLEnum, String, ForeignKey, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base_class import TimestampedBase


class PlacementStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Placement(TimestampedBase):
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id"))
    candidate_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancy.id"))
    status: Mapped[PlacementStatus] = mapped_column(SQLEnum(PlacementStatus), default=PlacementStatus.PENDING)
    
    # Invoice details
    invoice_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=50.00)  # Fixed $50 fee
    invoice_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    invoice_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    invoice_pdf_path: Mapped[Optional[str]] = mapped_column(type_=String(500), default=None)
    payment_due_date: Mapped[Optional[datetime]] = mapped_column(default=None)
    
    # Relationships
    application = relationship("Application", back_populates="placement")
    candidate = relationship("User", foreign_keys=[candidate_id])
    team = relationship("User", foreign_keys=[team_id])
    vacancy = relationship("Vacancy") 