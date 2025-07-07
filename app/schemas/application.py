from typing import Optional
from datetime import datetime

from schemas.base import BaseSchema, BasePaginatedSchema
from db.tables.application import ApplicationStatus


class ApplicationSchemaBase(BaseSchema):
    vacancy_id: int
    cover_letter: Optional[str] = None
    additional_notes: Optional[str] = None


class CreateApplicationSchema(ApplicationSchemaBase):
    pass


class UpdateApplicationSchema(BaseSchema):
    status: Optional[ApplicationStatus] = None
    cover_letter: Optional[str] = None
    additional_notes: Optional[str] = None


class OutApplicationSchema(ApplicationSchemaBase):
    id: int
    candidate_id: int
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime


class PaginatedApplicationSchema(BasePaginatedSchema[OutApplicationSchema]):
    items: list[OutApplicationSchema]


class ApplicationStatusUpdateSchema(BaseSchema):
    status: ApplicationStatus 