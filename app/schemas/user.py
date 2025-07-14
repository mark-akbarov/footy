from typing import Optional
from datetime import datetime
from pydantic import EmailStr, validator, field_validator

from schemas.base import BaseSchema, BasePaginatedSchema
from db.tables.user import UserRole


class UserSchemaBase(BaseSchema):
    first_name: str
    last_name: str
    email: EmailStr
    role: UserRole

    @field_validator('role', mode='before')
    @classmethod
    def normalize_role(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class CandidateRegistrationSchema(UserSchemaBase):
    password: str
    birthdate: Optional[datetime] = None
    position: Optional[str] = None
    experience_level: Optional[str] = None
    qualification: Optional[str] = None
    location: Optional[str] = None

    @field_validator('role')
    def validate_role(cls, v):
        if v != UserRole.CANDIDATE:
            raise ValueError('Role must be candidate for candidate registration')
        return v

    @field_validator('birthdate')
    def validate_birthdate(cls, v):
        if v and v.tzinfo is not None:
            # Convert timezone-aware datetime to timezone-naive (remove timezone info)
            return v.replace(tzinfo=None)
        return v


class TeamRegistrationSchema(UserSchemaBase):
    password: str
    club_name: str
    contact_phone: Optional[str] = None

    @field_validator('role')
    def validate_role(cls, v):
        if v != UserRole.TEAM:
            raise ValueError('Role must be team for team registration')
        return v


class UpdateUserSchema(BaseSchema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_approved: Optional[bool] = None

    # Candidate fields
    birthdate: Optional[datetime] = None
    position: Optional[str] = None
    experience_level: Optional[str] = None
    qualification: Optional[str] = None
    location: Optional[str] = None

    # Team fields
    club_name: Optional[str] = None
    contact_phone: Optional[str] = None

    @field_validator('birthdate')
    def validate_birthdate(cls, v):
        if v and v.tzinfo is not None:
            # Convert timezone-aware datetime to timezone-naive (remove timezone info)
            return v.replace(tzinfo=None)
        return v


class OutUserSchema(UserSchemaBase):
    id: int
    is_active: bool
    is_approved: bool
    email_verified: bool = False
    created_at: datetime
    updated_at: datetime

    # Candidate fields
    birthdate: Optional[datetime] = None
    position: Optional[str] = None
    experience_level: Optional[str] = None
    qualification: Optional[str] = None
    location: Optional[str] = None
    cv_file_path: Optional[str] = None

    # Team fields
    club_name: Optional[str] = None
    contact_phone: Optional[str] = None
    logo_file_path: Optional[str] = None

    @field_validator('birthdate', 'created_at', 'updated_at')
    def validate_datetime_fields(cls, v):
        if v and v.tzinfo is not None:
            # Convert timezone-aware datetime to timezone-naive (remove timezone info)
            return v.replace(tzinfo=None)
        return v


class PaginatedUserSchema(BasePaginatedSchema[OutUserSchema]):
    items: list[OutUserSchema]


class UserLoginSchema(BaseSchema):
    email: EmailStr
    password: str


class CandidateSearchSchema(BaseSchema):
    role: Optional[str] = None
    experience_level: Optional[str] = None
    location: Optional[str] = None
    position: Optional[str] = None
