from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import OAuth2PasswordBearer

from api.dependencies.database import DbSessionDep
from api.dependencies.pagination import PaginationDep
from db.crud.vacancy import VacancyCrud
from db.tables.user import UserRole
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


@router.post("", response_model=OutVacancySchema, status_code=status.HTTP_201_CREATED)
async def create_vacancy(
    vacancy_data: CreateVacancySchema,
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Create a new vacancy."""
    vacancy_crud = VacancyCrud(db)
    
    # Add team_id to vacancy data
    vacancy_dict = vacancy_data.model_dump()
    vacancy_dict["team_id"] = current_user.id
    
    vacancy = await vacancy_crud.create(vacancy_dict)
    await vacancy_crud.commit_session()
    
    return OutVacancySchema.model_validate(vacancy)


@router.get("", response_model=PaginatedVacancySchema)
async def list_vacancies(
    db: DbSessionDep,
    pagination: PaginationDep,
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
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Get all vacancies for the current team."""
    vacancy_crud = VacancyCrud(db)
    vacancies = await vacancy_crud.get_vacancies_by_team_id(current_user.id)
    
    return [OutVacancySchema.model_validate(v) for v in vacancies]


@router.get("/{vacancy_id}", response_model=OutVacancySchema)
async def get_vacancy(
    vacancy_id: int,
    db: DbSessionDep,
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


@router.put("/{vacancy_id}", response_model=OutVacancySchema)
async def update_vacancy(
    vacancy_id: int,
    vacancy_data: UpdateVacancySchema,
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Update a vacancy."""
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
            detail="You can only update your own vacancies"
        )
    
    updated_vacancy = await vacancy_crud.update_by_id(vacancy_id, vacancy_data)
    await vacancy_crud.commit_session()
    
    return OutVacancySchema.model_validate(updated_vacancy)


@router.delete("/{vacancy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vacancy(
    vacancy_id: int,
    db: DbSessionDep,
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
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Close a vacancy."""
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
            detail="You can only close your own vacancies"
        )
    
    closed_vacancy = await vacancy_crud.close_vacancy(vacancy_id)
    
    return OutVacancySchema.model_validate(closed_vacancy) 