from typing import Optional
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, field_validator

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
    price: Optional[Decimal] = None
    plan_type: Optional[MembershipPlan] = None
    stripe_subscription_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator('status', mode='before')
    @classmethod
    def normalize_status(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v

    @field_validator('plan_type', mode='before')
    @classmethod
    def normalize_plan(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class PaginatedMembershipSchema(BasePaginatedSchema[OutMembershipSchema]):
    items: list[OutMembershipSchema]
