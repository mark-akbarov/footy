from typing import Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel

from schemas.base import BaseSchema, BasePaginatedSchema
from db.tables.membership import MembershipPlan, MembershipStatus


class MembershipSchemaBase(BaseSchema):
    user_id: int
    plan_type: MembershipPlan
    price: Decimal
    start_date: datetime
    renewal_date: datetime


class CreateMembershipSchema(MembershipSchemaBase):
    pass


class UpdateMembershipSchema(BaseSchema):
    plan_type: Optional[MembershipPlan] = None
    status: Optional[MembershipStatus] = None
    price: Optional[Decimal] = None
    start_date: Optional[datetime] = None
    renewal_date: Optional[datetime] = None


class OutMembershipSchema(MembershipSchemaBase):
    id: int
    status: MembershipStatus
    stripe_subscription_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PaginatedMembershipSchema(BasePaginatedSchema[OutMembershipSchema]):
    items: list[OutMembershipSchema] 