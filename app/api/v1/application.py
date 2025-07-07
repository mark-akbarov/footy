from typing import List

from fastapi import APIRouter, HTTPException, Depends, status

from api.dependencies.database import DbSessionDep
from db.crud.application import ApplicationCrud
from db.crud.vacancy import VacancyCrud
from db.tables.user import UserRole
from schemas.application import (
    CreateApplicationSchema,
    UpdateApplicationSchema,
    OutApplicationSchema,
    ApplicationStatusUpdateSchema
)
from schemas.user import OutUserSchema
from api.v1.authentication import get_current_active_user

router = APIRouter(
    prefix="/applications",
    tags=["Applications"],
)


def require_candidate_role(current_user: OutUserSchema = Depends(get_current_active_user)) -> OutUserSchema:
    """Require user to be a candidate."""
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can perform this action"
        )
    return current_user


def require_team_role(current_user: OutUserSchema = Depends(get_current_active_user)) -> OutUserSchema:
    """Require user to be a team."""
    if current_user.role != UserRole.TEAM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teams can perform this action"
        )
    return current_user


@router.post("", response_model=OutApplicationSchema, status_code=status.HTTP_201_CREATED)
async def apply_to_vacancy(
    application_data: CreateApplicationSchema,
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Apply to a vacancy."""
    application_crud = ApplicationCrud(db)
    vacancy_crud = VacancyCrud(db)
    
    # Check if vacancy exists
    vacancy = await vacancy_crud.get_by_id(application_data.vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )
    
    # Check if candidate already applied
    existing_application = await application_crud.check_existing_application(
        current_user.id, application_data.vacancy_id
    )
    if existing_application:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already applied to this vacancy"
        )
    
    # Create application
    application_dict = application_data.model_dump()
    application_dict["candidate_id"] = current_user.id
    
    application = await application_crud.create(application_dict)
    await application_crud.commit_session()
    
    return OutApplicationSchema.model_validate(application)


@router.get("/my-applications", response_model=List[OutApplicationSchema])
async def get_my_applications(
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Get all applications for the current candidate."""
    application_crud = ApplicationCrud(db)
    applications = await application_crud.get_applications_by_candidate_id(current_user.id)
    
    return [OutApplicationSchema.model_validate(app) for app in applications]


@router.get("/pending", response_model=List[OutApplicationSchema])
async def get_pending_applications(
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Get all pending applications for the current team's vacancies."""
    application_crud = ApplicationCrud(db)
    applications = await application_crud.get_pending_applications_by_team(current_user.id)
    
    return [OutApplicationSchema.model_validate(app) for app in applications]


@router.get("/vacancy/{vacancy_id}", response_model=List[OutApplicationSchema])
async def get_applications_for_vacancy(
    vacancy_id: int,
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Get all applications for a specific vacancy."""
    application_crud = ApplicationCrud(db)
    vacancy_crud = VacancyCrud(db)
    
    # Check if vacancy exists and belongs to current team
    vacancy = await vacancy_crud.get_by_id(vacancy_id)
    if not vacancy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vacancy not found"
        )
    
    if vacancy.team_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view applications for your own vacancies"
        )
    
    applications = await application_crud.get_applications_by_vacancy_id(vacancy_id)
    
    return [OutApplicationSchema.model_validate(app) for app in applications]


@router.patch("/{application_id}/status", response_model=OutApplicationSchema)
async def update_application_status(
    application_id: int,
    status_data: ApplicationStatusUpdateSchema,
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Update application status (accept/decline)."""
    application_crud = ApplicationCrud(db)
    vacancy_crud = VacancyCrud(db)
    
    # Get application
    application = await application_crud.get_by_id(application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check if the vacancy belongs to the current team
    vacancy = await vacancy_crud.get_by_id(application.vacancy_id)
    if not vacancy or vacancy.team_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update applications for your own vacancies"
        )
    
    # Update application status
    updated_application = await application_crud.update_application_status(
        application_id, status_data.status
    )
    
    return OutApplicationSchema.model_validate(updated_application)


@router.get("/{application_id}", response_model=OutApplicationSchema)
async def get_application(
    application_id: int,
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(get_current_active_user)
):
    """Get a specific application."""
    application_crud = ApplicationCrud(db)
    vacancy_crud = VacancyCrud(db)
    
    application = await application_crud.get_by_id(application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check if user has permission to view this application
    if current_user.role == UserRole.CANDIDATE:
        if application.candidate_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own applications"
            )
    elif current_user.role == UserRole.TEAM:
        vacancy = await vacancy_crud.get_by_id(application.vacancy_id)
        if not vacancy or vacancy.team_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view applications for your own vacancies"
            )
    
    return OutApplicationSchema.model_validate(application)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_application(
    application_id: int,
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Withdraw an application."""
    application_crud = ApplicationCrud(db)
    
    application = await application_crud.get_by_id(application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    if application.candidate_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only withdraw your own applications"
        )
    
    await application_crud.delete_by_id(application_id)
    await application_crud.commit_session() 