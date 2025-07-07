from typing import List, Optional
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, status, Query, UploadFile, File
from fastapi.responses import FileResponse

from api.dependencies.database import DbSessionDep
from api.dependencies.pagination import PaginationDep
from db.crud.user import UsersCrud
from db.tables.user import UserRole
from schemas.user import (
    OutUserSchema,
    PaginatedUserSchema,
    CandidateSearchSchema
)
from api.v1.authentication import get_current_active_user
from core.config import settings

router = APIRouter(
    prefix="/candidates",
    tags=["Candidates"],
)


def require_team_role(current_user: OutUserSchema = Depends(get_current_active_user)) -> OutUserSchema:
    """Require user to be a team."""
    if current_user.role != UserRole.TEAM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teams can access candidate profiles"
        )
    if not current_user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team must be approved to access candidate profiles"
        )
    return current_user


@router.get("", response_model=PaginatedUserSchema)
async def search_candidates(
    db: DbSessionDep,
    pagination: PaginationDep,
    current_user: OutUserSchema = Depends(require_team_role),
    role: Optional[str] = Query(None, description="Filter by role/position"),
    location: Optional[str] = Query(None, description="Filter by location"),
    experience_level: Optional[str] = Query(None, description="Filter by experience level"),
    position: Optional[str] = Query(None, description="Filter by position")
):
    """Search and browse candidates."""
    user_crud = UsersCrud(db)
    
    search_params = CandidateSearchSchema(
        role=role,
        location=location,
        experience_level=experience_level,
        position=position
    )
    
    candidates = await user_crud.search_candidates(
        search_params,
        limit=pagination.limit,
        offset=pagination.offset
    )
    
    # Count total for pagination
    # In a real app, you'd want a proper count query
    total_candidates = await user_crud.get_candidates(limit=1000)  # This is inefficient for large datasets
    
    return PaginatedUserSchema(
        items=[OutUserSchema.model_validate(c) for c in candidates],
        total=len(total_candidates),
        limit=pagination.limit,
        offset=pagination.offset
    )


@router.get("/with-memberships", response_model=List[OutUserSchema])
async def get_candidates_with_active_memberships(
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Get candidates with active memberships (premium feature)."""
    user_crud = UsersCrud(db)
    candidates = await user_crud.get_candidates_with_active_membership()
    
    return [OutUserSchema.model_validate(c) for c in candidates]


@router.get("/{candidate_id}", response_model=OutUserSchema)
async def get_candidate_profile(
    candidate_id: int,
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Get detailed candidate profile."""
    user_crud = UsersCrud(db)
    
    candidate = await user_crud.get_by_id(candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    if candidate.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a candidate"
        )
    
    if not candidate.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile is not active"
        )
    
    return OutUserSchema.model_validate(candidate)


@router.get("/{candidate_id}/cv")
async def get_candidate_cv(
    candidate_id: int,
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Get candidate CV file (if uploaded)."""
    user_crud = UsersCrud(db)
    
    candidate = await user_crud.get_by_id(candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    if candidate.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a candidate"
        )
    
    if not candidate.cv_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No CV file uploaded for this candidate"
        )
    
    # In a real implementation, you'd serve the file from storage
    return {
        "message": "CV file access would be implemented here",
        "file_path": candidate.cv_file_path,
        "download_url": f"/files/cv/{candidate_id}"
    }


@router.get("/search/by-position/{position_name}", response_model=List[OutUserSchema])
async def search_candidates_by_position(
    position_name: str,
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role),
    limit: int = Query(20, le=100)
):
    """Search candidates by specific position."""
    user_crud = UsersCrud(db)
    
    search_params = CandidateSearchSchema(position=position_name)
    candidates = await user_crud.search_candidates(search_params, limit=limit)
    
    return [OutUserSchema.model_validate(c) for c in candidates]


@router.get("/featured", response_model=List[OutUserSchema])
async def get_featured_candidates(
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role),
    limit: int = Query(10, le=20)
):
    """Get featured candidates (with premium memberships)."""
    user_crud = UsersCrud(db)
    
    # Get candidates with active memberships as featured
    featured_candidates = await user_crud.get_candidates_with_active_membership()
    
    return [OutUserSchema.model_validate(c) for c in featured_candidates[:limit]]


def require_candidate_role(current_user: OutUserSchema = Depends(get_current_active_user)) -> OutUserSchema:
    """Require user to be a candidate."""
    if current_user.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only candidates can perform this action"
        )
    return current_user


@router.post("/upload-cv")
async def upload_cv(
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_candidate_role),
    file: UploadFile = File(...)
):
    """Upload CV file for the current candidate."""
    user_crud = UsersCrud(db)
    
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded"
        )
    
    # Validate file type
    allowed_extensions = ['.pdf', '.doc', '.docx']
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, DOC, and DOCX files are allowed"
        )
    
    # Create upload directory if it doesn't exist
    upload_dir = os.path.join(settings.UPLOAD_DIR, "cvs")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate a unique filename
    filename = f"{current_user.id}_{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(upload_dir, filename)
    
    # Save the file
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Update the candidate's CV file path
    user = await user_crud.get_by_id(current_user.id)
    if user:
        user.cv_file_path = file_path
        await user_crud.commit_session()
    
    return {
        "message": "CV file uploaded successfully",
        "filename": filename,
        "download_url": f"/api/v1/candidates/download-cv/{current_user.id}"
    }


@router.get("/download-cv/{candidate_id}")
async def download_cv(
    candidate_id: int,
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Download a candidate's CV file."""
    user_crud = UsersCrud(db)
    
    candidate = await user_crud.get_by_id(candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    if candidate.role != UserRole.CANDIDATE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a candidate"
        )
    
    if not candidate.cv_file_path or not os.path.exists(candidate.cv_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV file not found"
        )
    
    filename = os.path.basename(candidate.cv_file_path)
    return FileResponse(
        path=candidate.cv_file_path,
        filename=f"{candidate.first_name}_{candidate.last_name}_CV.pdf",
        media_type="application/octet-stream"
    )


@router.get("/my-cv")
async def get_my_cv(
    db: DbSessionDep,
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Get current candidate's CV information."""
    user_crud = UsersCrud(db)
    
    user = await user_crud.get_by_id(current_user.id)
    if not user or not user.cv_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV file not found"
        )
    
    return {
        "cv_uploaded": True,
        "filename": os.path.basename(user.cv_file_path),
        "download_url": f"/api/v1/candidates/download-cv/{current_user.id}"
    } 