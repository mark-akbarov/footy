from typing import Optional
from datetime import datetime
from decimal import Decimal

from pydantic import field_validator

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

    @field_validator("expiry_date")
    def remove_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo:
            return value.replace(tzinfo=None)
        return value


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

    @field_validator("status", mode="before")
    def transform_status_to_lowercase(cls, value: str) -> str:
        # Transform DB uppercase values to lowercase for API response
        return value.lower() if isinstance(value, str) else value


class OutVacancyListSchema(VacancySchemaBase):
    id: int
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None
    status: VacancyStatus
    team_id: int
    team_name: Optional[str] = None  # Added team_name field
    created_at: datetime
    updated_at: datetime

    @field_validator("status", mode="before")
    def transform_status_to_lowercase(cls, value: str) -> str:
        # Transform DB uppercase values to lowercase for API response
        return value.lower() if isinstance(value, str) else value


class PaginatedVacancySchema(BasePaginatedSchema[OutVacancySchema]):
    items: list[OutVacancySchema]


class PaginatedVacancyListSchema(BasePaginatedSchema[OutVacancyListSchema]):
    items: list[OutVacancyListSchema]


class VacancySearchSchema(BaseSchema):
    role: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[Decimal] = None
    salary_max: Optional[Decimal] = None
    experience_level: Optional[str] = None
    position_type: Optional[str] = None
