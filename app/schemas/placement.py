from typing import Optional
from datetime import datetime
from decimal import Decimal

from schemas.base import BaseSchema, BasePaginatedSchema
from db.tables.placement import PlacementStatus


class PlacementSchemaBase(BaseSchema):
    application_id: int
    candidate_id: int
    team_id: int
    vacancy_id: int


class CreatePlacementSchema(PlacementSchemaBase):
    pass


class UpdatePlacementSchema(BaseSchema):
    status: Optional[PlacementStatus] = None
    invoice_amount: Optional[Decimal] = None
    payment_due_date: Optional[datetime] = None


class OutPlacementSchema(PlacementSchemaBase):
    id: int
    status: PlacementStatus
    invoice_amount: Decimal
    invoice_generated: bool
    invoice_paid: bool
    invoice_pdf_path: Optional[str] = None
    payment_due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PaginatedPlacementSchema(BasePaginatedSchema[OutPlacementSchema]):
    items: list[OutPlacementSchema]


class PlacementConfirmationSchema(BaseSchema):
    application_id: int 