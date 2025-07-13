from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base_class import TimestampedBase


class Message(TimestampedBase):
    sender_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    receiver_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    subject: Mapped[Optional[str]] = mapped_column(type_=String(255), default=None)
    content: Mapped[str] = mapped_column(type_=Text())
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_message_id: Mapped[Optional[int]] = mapped_column(ForeignKey("message.id"), default=None)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
    parent_message = relationship("Message", remote_side="Message.id")
    replies = relationship("Message", back_populates="parent_message") 