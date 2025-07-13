import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Enum as SQLEnum, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base_class import TimestampedBase


class UserRole(str, enum.Enum):
    CANDIDATE = "candidate"
    TEAM = "team"
    ADMIN = "admin"


class User(TimestampedBase):
    first_name: Mapped[str] = mapped_column()
    last_name: Mapped[str] = mapped_column()
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(type_=String(255))
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole))
    is_active: Mapped[bool] = mapped_column(default=False)
    is_approved: Mapped[bool] = mapped_column(default=False)  # For teams approval
    email_verified: Mapped[bool] = mapped_column(default=False)  # Track email verification
    
    # Candidate-specific fields
    birthdate: Mapped[Optional[datetime]] = mapped_column(default=None)
    position: Mapped[Optional[str]] = mapped_column(type_=String(255), default=None)
    experience_level: Mapped[Optional[str]] = mapped_column(type_=String(255), default=None)
    qualification: Mapped[Optional[str]] = mapped_column(type_=Text(), default=None)
    location: Mapped[Optional[str]] = mapped_column(type_=String(255), default=None)
    cv_file_path: Mapped[Optional[str]] = mapped_column(type_=String(500), default=None)
    
    # Team-specific fields
    club_name: Mapped[Optional[str]] = mapped_column(type_=String(255), default=None)
    contact_phone: Mapped[Optional[str]] = mapped_column(type_=String(50), default=None)
    logo_file_path: Mapped[Optional[str]] = mapped_column(type_=String(500), default=None)
    
    # Relationships
    memberships = relationship("Membership", back_populates="user")
    applications = relationship("Application", back_populates="candidate")
    vacancies = relationship("Vacancy", back_populates="team")
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")
