import enum
from datetime import datetime

from sqlalchemy import Enum as SQLEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base_class import TimestampedBase


class User(TimestampedBase):
    first_name: Mapped[str] = mapped_column()
    last_name: Mapped[str] = mapped_column()
    birthdate: Mapped[datetime] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=False)
    email: Mapped[str] = mapped_column()
    hashed_password: Mapped[str] = mapped_column(type_=String(255))
    position: Mapped[str] = mapped_column(type_=String(255))
    experience_level: Mapped[str] = mapped_column(type_=String(255))
    qualification: Mapped[str] = mapped_column(type_=Text())
