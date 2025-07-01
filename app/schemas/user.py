from typing import Optional
from datetime import datetime
from schemas.base import BaseSchema, BasePaginatedSchema


class UserSchemaBase(BaseSchema):
    first_name: str
    last_name: str
    username: str
    birthdate: datetime
    role: str
    is_active: bool
    email: str


class UpdateUserSchema(BaseSchema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    birthdate: Optional[datetime] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    email: Optional[str] = None


class InUserSchema(UserSchemaBase):
    ...


class OutUserSchema(UserSchemaBase):
    id: int
    created_at: datetime
    updated_at: datetime


class PaginatedUsertSchema(BasePaginatedSchema[OutUserSchema]):
    items: list[OutUserSchema]
