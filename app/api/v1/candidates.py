from io import BytesIO
from typing import List, Optional
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, status, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db_session
from api.dependencies.pagination import PaginationDep
from api.dependencies.user import get_current_active_user
from db.crud.membership import MembershipCrud
from db.crud.user import UsersCrud
from db.tables.user import UserRole
from schemas.user import (
    OutUserSchema,
    PaginatedUserSchema,
    CandidateSearchSchema
)

from core.config import settings
from utils.s3 import upload_cv_to_s3, generate_presigned_url, delete_file_from_s3

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
    pagination: PaginationDep,
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_team_role)
):
    """Get candidates with active memberships (premium feature)."""
    user_crud = UsersCrud(db)
    candidates = await user_crud.get_candidates_with_active_membership()

    return [OutUserSchema.model_validate(c) for c in candidates]


@router.get("/{candidate_id}", response_model=OutUserSchema)
async def get_candidate_profile(
    candidate_id: int,
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_candidate_role),
    file: UploadFile = File(...)
):
    user_crud = UsersCrud(db)
    membership_crud = MembershipCrud(db)

    # Check if user has active membership
    active_membership = await membership_crud.get_active_membership_by_user_id(current_user.id)
    if not active_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active membership required to upload CV. Please purchase a membership first."
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded"
        )

    allowed_extensions = ['.pdf', '.doc', '.docx']
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, DOC, and DOCX files are allowed"
        )

    # Read file into memory
    content = await file.read()

    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds limit of {settings.MAX_FILE_SIZE // (1024 * 1024)}MB"
        )

    # Get actual user model from DB
    user = await user_crud.get_model_by_id(current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Delete previous CV if exists
    if user.cv_file_path:
        try:
            delete_file_from_s3(user.cv_file_path)
        except Exception as e:
            print(f"Warning: Failed to delete old CV from S3: {e}")

    # Upload new CV and update user in a transaction
    try:
        s3_key = upload_cv_to_s3(
            file_obj=BytesIO(content),
            filename=file.filename,
            content_type=file.content_type
        )
        user.cv_file_path = s3_key
        await user_crud.commit_session()  # Use the CRUD's commit method
    except Exception as e:
        print(f"Error uploading to S3 or updating DB: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing file"
        )

    download_url = generate_presigned_url(s3_key)

    return {
        "message": "CV file uploaded successfully",
        "filename": file.filename,
        "file_size": len(content),
        "file_path": s3_key,
        "download_url": download_url
    }


@router.get("/download-cv/{user_id}")
async def download_cv(
    user_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Generate a presigned URL to download the CV from S3."""
    from utils.s3 import generate_presigned_url

    user_crud = UsersCrud(db)

    # Get user
    user = await user_crud.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Only allow user to access their own CV
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You can only download your own CV")

    # Check CV exists
    if not user.cv_file_path:
        raise HTTPException(status_code=404, detail="CV file not found")

    try:
        presigned_url = generate_presigned_url(user.cv_file_path)
    except Exception as e:
        print(f"Failed to generate S3 download link: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate download URL")

    return {
        "message": "Presigned download link generated",
        "url": presigned_url
    }


@router.delete("/delete-cv")
async def delete_cv(
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Delete CV file from S3 for the current candidate."""
    from utils.s3 import delete_file_from_s3

    user_crud = UsersCrud(db)

    # Get user
    user = await user_crud.get_model_by_id(current_user.id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if CV exists
    if not user.cv_file_path:
        raise HTTPException(status_code=404, detail="No CV file found")

    # Attempt to delete from S3
    try:
        delete_file_from_s3(user.cv_file_path)
        print(f"Deleted CV from S3: {user.cv_file_path}")
    except Exception as e:
        print(f"Error deleting from S3: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete CV from storage")

    # Clear path from DB
    try:
        user.cv_file_path = None
        await user_crud.commit_session()
        print(f"Removed CV path from DB for user {current_user.id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update user profile")

    return {"message": "CV file deleted successfully"}


@router.get("/cv-info")
async def get_cv_info(
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Get CV file information for the current candidate."""
    user_crud = UsersCrud(db)

    # Get current user
    user = await user_crud.get_by_id(current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user has CV file
    if not user.cv_file_path or not os.path.exists(user.cv_file_path):
        return {
            "has_cv": False,
            "message": "No CV file found"
        }

    # Get file info
    try:
        file_stat = os.stat(user.cv_file_path)
        filename = os.path.basename(user.cv_file_path)
        file_extension = os.path.splitext(filename)[1]

        return {
            "has_cv": True,
            "filename": filename,
            "file_size": file_stat.st_size,
            "file_extension": file_extension,
            "upload_date": file_stat.st_mtime,
            "download_url": f"/api/v1/candidates/download-cv/{current_user.id}"
        }
    except Exception as e:
        print(f"Error getting CV file info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving CV file information"
        )


@router.get("/download-cv/{candidate_id}")
async def download_cv(
    candidate_id: int,
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
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
        "file_size": os.path.getsize(user.cv_file_path) if os.path.exists(user.cv_file_path) else 0,
        "download_url": f"/api/v1/candidates/download-cv/{current_user.id}"
    }


@router.delete("/my-cv")
async def delete_my_cv(
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_candidate_role)
):
    """Delete current candidate's CV file."""
    user_crud = UsersCrud(db)

    user = await user_crud.get_by_id(current_user.id)
    if not user or not user.cv_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV file not found"
        )

    # Remove the file from storage
    if os.path.exists(user.cv_file_path):
        try:
            os.remove(user.cv_file_path)
        except OSError:
            pass  # Ignore errors if file doesn't exist

    # Clear the file path from database
    user.cv_file_path = None
    await user_crud.commit_session()

    return {
        "message": "CV file deleted successfully"
    }
