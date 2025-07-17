from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db_session
from api.dependencies.pagination import PaginationDep
from db.crud.vacancy import VacancyCrud
from db.tables.user import UserRole
from db.tables.vacancy import VacancyStatus, Vacancy
from schemas.vacancy import (
    CreateVacancySchema,
    UpdateVacancySchema,
    OutVacancySchema,
    PaginatedVacancySchema,
    VacancySearchSchema
)
from schemas.user import OutUserSchema
from api.v1.authentication import get_current_active_user

router = APIRouter(
    prefix="/vacancies",
    tags=["Vacancies"],
)


def require_team_role(current_user: OutUserSchema = Depends(get_current_active_user)) -> OutUserSchema:
    """Require user to be a team."""
    if current_user.role != UserRole.TEAM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teams can perform this action"
        )
    if not current_user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team must be approved to perform this action"
        )
    return current_user


from datetime import datetime


@router.post("", response_model=OutVacancySchema, status_code=status.HTTP_201_CREATED)
async def create_vacancy(
    vacancy_data: CreateVacancySchema,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Create a new vacancy."""
    vacancy_crud = VacancyCrud(db)

    # Convert Pydantic model to dict
    vacancy_dict = vacancy_data.model_dump()

    # Ensure expiry_date is UTC without tzinfo
    expiry_date = vacancy_dict.get("expiry_date")
    if expiry_date and isinstance(expiry_date, datetime) and expiry_date.tzinfo:
        expiry_date = expiry_date.astimezone(datetime.timezone.utc)  # Convert to UTC
        vacancy_dict["expiry_date"] = expiry_date.replace(tzinfo=None)  # Remove tzinfo

    # Add team_id
    vacancy_dict["team_id"] = current_user.id

    # Create the vacancy
    vacancy = await vacancy_crud.create(vacancy_dict)
    await vacancy_crud.commit_session()

    return OutVacancySchema.model_validate(vacancy)


@router.get("", response_model=PaginatedVacancySchema)
async def list_vacancies(
    pagination: PaginationDep,
    db: AsyncSession = Depends(get_db_session),
    role: Optional[str] = Query(None, description="Filter by role/position"),
    location: Optional[str] = Query(None, description="Filter by location"),
    salary_min: Optional[float] = Query(None, description="Minimum salary"),
    salary_max: Optional[float] = Query(None, description="Maximum salary"),
    experience_level: Optional[str] = Query(None, description="Filter by experience level"),
    position_type: Optional[str] = Query(None, description="Filter by position type")
):
    """List all active vacancies with optional filters."""
    vacancy_crud = VacancyCrud(db)

    search_params = VacancySearchSchema(
        role=role,
        location=location,
        salary_min=salary_min,
        salary_max=salary_max,
        experience_level=experience_level,
        position_type=position_type
    )

    vacancies = await vacancy_crud.search_vacancies(
        search_params,
        limit=pagination.limit,
        offset=pagination.offset
    )

    return PaginatedVacancySchema(
        items=[OutVacancySchema.model_validate(v) for v in vacancies],
        total=len(vacancies),
        limit=pagination.limit,
        offset=pagination.offset
    )


@router.get("/my-vacancies", response_model=List[OutVacancySchema])
async def get_my_vacancies(
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Get all vacancies for the current team."""
    vacancy_crud = VacancyCrud(db)
    vacancies = await vacancy_crud.get_vacancies_by_team_id(current_user.id)

    return [OutVacancySchema.model_validate(v) for v in vacancies]


@router.get("/vacancies/active", response_model=List[OutVacancySchema])
async def get_my_vacancies(
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Get all vacancies for the current team."""
    vacancy_crud = VacancyCrud(db)
    vacancies = await vacancy_crud.get_active_vacancies(team_id=current_user.id)

    # Convert ORM models to Pydantic schemas
    return [OutVacancySchema.model_validate(v) for v in vacancies]


@router.get("/{vacancy_id}", response_model=OutVacancySchema)
async def get_vacancy(
    vacancy_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(get_current_active_user)
):
    """Get a specific vacancy."""
    vacancy_crud = VacancyCrud(db)
    vacancy = await vacancy_crud.get_by_id(vacancy_id)

    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    return OutVacancySchema.model_validate(vacancy)


@router.post("/vacancies/activate", response_model=OutVacancySchema)
async def activate_vacancy(
    vacancy_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Activate a specific vacancy."""

    # Query the vacancy directly using SQLAlchemy
    result = await db.execute(
        select(Vacancy).where(Vacancy.id == vacancy_id)
    )
    vacancy = result.scalars().first()

    # Ensure the vacancy exists
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    # Ensure the current user is the owner of the vacancy
    if vacancy.team_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only activate your own vacancies"
        )

    # Change the vacancy status to ACTIVE
    vacancy.status = VacancyStatus.ACTIVE
    await db.commit()
    await db.refresh(vacancy)

    # Convert to Pydantic schema before returning
    return OutVacancySchema.model_validate(vacancy)


@router.put("/{vacancy_id}", response_model=OutVacancySchema)
async def update_vacancy(
    vacancy_id: int,
    vacancy_data: UpdateVacancySchema,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_team_role)
):
    vacancy_crud = VacancyCrud(db)

    # First, check if the vacancy exists
    existing_vacancy = await vacancy_crud.get_by_id(vacancy_id)
    if not existing_vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    # Now, update the vacancy
    updated_vacancy = await vacancy_crud.update(
        obj_id=vacancy_id,
        schema=vacancy_data,
        author_id=current_user.id
    )

    if not updated_vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy could not be updated"
        )

    return OutVacancySchema.model_validate(updated_vacancy)

@router.delete("/{vacancy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vacancy(
    vacancy_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Delete a vacancy."""
    vacancy_crud = VacancyCrud(db)
    vacancy = await vacancy_crud.get_by_id(vacancy_id)

    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    if vacancy.team_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own vacancies"
        )

    await vacancy_crud.delete_by_id(vacancy_id)
    await vacancy_crud.commit_session()


@router.post("/{vacancy_id}/close", response_model=OutVacancySchema)
async def close_vacancy(
    vacancy_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Close a vacancy."""
    vacancy_crud = VacancyCrud(db)

    # Fetch the vacancy
    vacancy = await vacancy_crud.get_by_id(vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )

    # Check ownership
    if vacancy.team_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only close your own vacancies"
        )

    # Close the vacancy
    closed_vacancy = await vacancy_crud.close_vacancy(vacancy_id)

    return closed_vacancy
