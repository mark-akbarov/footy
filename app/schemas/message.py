from typing import Optional
from datetime import datetime

from schemas.base import BaseSchema, BasePaginatedSchema


class MessageSchemaBase(BaseSchema):
    receiver_id: int
    content: str
    subject: Optional[str] = None
    parent_message_id: Optional[int] = None


class CreateMessageSchema(MessageSchemaBase):
    pass


class UpdateMessageSchema(BaseSchema):
    is_read: Optional[bool] = None


class OutMessageSchema(MessageSchemaBase):
    id: int
    sender_id: int
    is_read: bool
    created_at: datetime
    updated_at: datetime


class PaginatedMessageSchema(BasePaginatedSchema[OutMessageSchema]):
    items: list[OutMessageSchema]


class MessageThreadSchema(BaseSchema):
    user_id: int
    user_name: str
    user_role: str
    last_message: str
    last_message_time: datetime
    unread_count: int 