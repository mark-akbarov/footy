from typing import List

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db_session
from api.dependencies.pagination import PaginationDep
from db.crud.user import UsersCrud
from db.crud.placement import PlacementCrud
from db.crud.membership import MembershipCrud
from db.tables.user import UserRole
from schemas.user import OutUserSchema, PaginatedUserSchema, UpdateUserSchema
from schemas.placement import OutPlacementSchema
from api.v1.authentication import get_current_active_user

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


def require_admin_role(current_user: OutUserSchema = Depends(get_current_active_user)) -> OutUserSchema:
    """Require user to be an admin."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("/teams/pending", response_model=List[OutUserSchema])
async def get_pending_teams(
        db: AsyncSession = Depends(get_db_session),
        current_user: OutUserSchema = Depends(require_admin_role)
):
    """Get all teams pending approval."""
    user_crud = UsersCrud(db)
    teams = await user_crud.get_unapproved_teams()

    return [OutUserSchema.model_validate(team) for team in teams]


@router.post("/teams/{team_id}/approve", response_model=OutUserSchema)
async def approve_team(
        team_id: int,
        db: AsyncSession = Depends(get_db_session),
        current_user: OutUserSchema = Depends(require_admin_role)
):
    """Approve a team."""
    user_crud = UsersCrud(db)

    team = await user_crud.get_by_id(team_id)
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    if team.role != UserRole.TEAM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a team"
        )

    approved_team = await user_crud.approve_team(team_id)

    return OutUserSchema.model_validate(approved_team)


@router.get("/users", response_model=PaginatedUserSchema)
async def get_all_users(
        pagination: PaginationDep,
        current_user: OutUserSchema = Depends(require_admin_role),
        db: AsyncSession = Depends(get_db_session),
):
    """Get all users with pagination."""
    user_crud = UsersCrud(db)
    users = await user_crud.get_all(limit=pagination.limit, offset=pagination.offset)
    total = await user_crud.count()

    return PaginatedUserSchema(
        items=[OutUserSchema.model_validate(user) for user in users],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset
    )


@router.get("/users/{user_id}", response_model=OutUserSchema)
async def get_user_by_id(
        user_id: int,
        db: AsyncSession = Depends(get_db_session),
        current_user: OutUserSchema = Depends(require_admin_role)
):
    """Get a specific user by ID."""
    user_crud = UsersCrud(db)
    user = await user_crud.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return OutUserSchema.model_validate(user)


@router.patch("/users/{user_id}", response_model=OutUserSchema)
async def update_user(
        user_id: int,
        user_data: UpdateUserSchema,
        db: AsyncSession = Depends(get_db_session),
        current_user: OutUserSchema = Depends(require_admin_role)
):
    """Update user information."""
    user_crud = UsersCrud(db)

    user = await user_crud.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    updated_user = await user_crud.update_by_id(user_id, user_data)
    await user_crud.commit_session()

    return OutUserSchema.model_validate(updated_user)


@router.post("/users/{user_id}/activate", response_model=OutUserSchema)
async def activate_user(
        user_id: int,
        db: AsyncSession = Depends(get_db_session),
        current_user: OutUserSchema = Depends(require_admin_role)
):
    """Activate a user account."""
    user_crud = UsersCrud(db)

    user = await user_crud.activate_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return OutUserSchema.model_validate(user)


@router.post("/users/{user_id}/deactivate", response_model=OutUserSchema)
async def deactivate_user(
        user_id: int,
        db: AsyncSession = Depends(get_db_session),
        current_user: OutUserSchema = Depends(require_admin_role)
):
    """Deactivate a user account."""
    user_crud = UsersCrud(db)

    user = await user_crud.deactivate_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return OutUserSchema.model_validate(user)


@router.get("/revenue")
async def get_revenue_stats(
        db: AsyncSession = Depends(get_db_session),
        current_user: OutUserSchema = Depends(require_admin_role)
):
    """Get revenue statistics."""
    membership_crud = MembershipCrud(db)
    placement_crud = PlacementCrud(db)

    # Get all paid memberships
    # This would need more sophisticated querying in a real app

    return {
        "message": "Revenue tracking would be implemented here",
        "candidate_subscriptions": "Sum of all membership payments",
        "team_placement_fees": "Sum of all placement invoices paid",
        "total_revenue": "Combined revenue from all sources"
    }


@router.get("/stats")
async def get_platform_stats(
        db: AsyncSession = Depends(get_db_session),
        current_user: OutUserSchema = Depends(require_admin_role)
):
    """Get platform statistics."""
    user_crud = UsersCrud(db)

    # Get basic stats
    total_users = await user_crud.count()

    # In a real implementation, you'd want to optimize these queries
    candidates = await user_crud.get_candidates(limit=1000)
    teams = await user_crud.get_teams(limit=1000)

    return {
        "total_users": total_users,
        "total_candidates": len(candidates),
        "total_teams": len(teams),
        "active_candidates": len([c for c in candidates if c.is_active]),
        "active_teams": len([t for t in teams if t.is_active and t.is_approved]),
        "pending_team_approvals": len(await user_crud.get_unapproved_teams())
    }


@router.delete("/users/{user_id}")
async def delete_user(
        user_id: int,
        db: AsyncSession = Depends(get_db_session),
        current_user: OutUserSchema = Depends(require_admin_role)
):
    """Delete a user account (use with caution)."""
    user_crud = UsersCrud(db)

    user = await user_crud.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Don't allow deleting admin users
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete admin users"
        )

    await user_crud.delete_by_id(user_id)
    await user_crud.commit_session()

    return {"message": "User deleted successfully"}
