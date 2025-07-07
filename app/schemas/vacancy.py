from typing import Optional
from datetime import datetime
from decimal import Decimal

from schemas.base import BaseSchema, BasePaginatedSchema
from db.tables.vacancy import VacancyStatus


class VacancySchemaBase(BaseSchema):
    title: str
    description: str
    requirements: str
    location: str
    position_type: str
    experience_level: str
    expiry_date: datetime


class CreateVacancySchema(VacancySchemaBase):
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None


class UpdateVacancySchema(BaseSchema):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None
    location: Optional[str] = None
    position_type: Optional[str] = None
    experience_level: Optional[str] = None
    expiry_date: Optional[datetime] = None
    status: Optional[VacancyStatus] = None


class OutVacancySchema(VacancySchemaBase):
    id: int
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None
    status: VacancyStatus
    team_id: int
    created_at: datetime
    updated_at: datetime


class PaginatedVacancySchema(BasePaginatedSchema[OutVacancySchema]):
    items: list[OutVacancySchema]


class VacancySearchSchema(BaseSchema):
    role: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None
    experience_level: Optional[str] = None
    position_type: Optional[str] = None 