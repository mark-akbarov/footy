import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Enum as SQLEnum, String, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base_class import TimestampedBase


class MembershipPlan(str, enum.Enum):
    BASIC = "basic"
    PREMIUM = "premium"
    PROFESSIONAL = "professional"


class MembershipStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"


class Membership(TimestampedBase):
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    plan_type: Mapped[MembershipPlan] = mapped_column(SQLEnum(MembershipPlan))
    status: Mapped[MembershipStatus] = mapped_column(SQLEnum(MembershipStatus), default=MembershipStatus.PENDING)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    start_date: Mapped[datetime] = mapped_column()
    renewal_date: Mapped[datetime] = mapped_column()
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(type_=String(255), default=None)
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(type_=String(255), default=None)
    
    # Relationships
    user = relationship("User", back_populates="memberships") 