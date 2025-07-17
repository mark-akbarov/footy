from typing import Type, Optional, List

from pydantic import EmailStr
from sqlalchemy.sql.elements import UnaryExpression
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from db.crud.base import BaseCrud
from db.tables.user import User as UserTable, UserRole
from schemas.user import (
    UpdateUserSchema,
    OutUserSchema,
    PaginatedUserSchema,
    CandidateRegistrationSchema,
    TeamRegistrationSchema,
    CandidateSearchSchema
)


class UsersCrud(
    BaseCrud[
        CandidateRegistrationSchema,
        UpdateUserSchema,
        OutUserSchema,
        PaginatedUserSchema,
        UserTable,
    ]
):
    @property
    def _table(self) -> Type[UserTable]:
        return UserTable

    @property
    def _out_schema(self) -> Type[OutUserSchema]:
        return OutUserSchema

    @property
    def default_ordering(self) -> UnaryExpression:
        return UserTable.created_at.desc()

    @property
    def _paginated_schema(self) -> Type[PaginatedUserSchema]:
        return PaginatedUserSchema

    async def get_model_by_id(self, user_id: int) -> UserTable | None:
        result = await self._db_session.execute(
            select(UserTable).where(UserTable.id == user_id, UserTable.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[UserTable]:
        """Get user by email."""
        try:
            stmt = select(self._table).where(self._table.email == email)
            result = await self._db_session.execute(stmt)
            user = result.scalar_one_or_none()
            return user
        except Exception as e:
            print(f"Error in get_by_email: {str(e)}")
            return None

    async def get_candidates(self, limit: int = 20, offset: int = 0) -> List[UserTable]:
        """Get all candidates."""
        query = select(UserTable).where(
            and_(
                UserTable.role == UserRole.CANDIDATE,
                UserTable.is_active == True
            )
        ).limit(limit).offset(offset)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_teams(self, limit: int = 20, offset: int = 0) -> List[UserTable]:
        """Get all teams."""
        query = select(UserTable).where(
            and_(
                UserTable.role == UserRole.TEAM,
                UserTable.is_active == True
            )
        ).limit(limit).offset(offset)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_unapproved_teams(self) -> List[UserTable]:
        """Get all unapproved teams."""
        query = select(UserTable).where(
            and_(
                UserTable.role == UserRole.TEAM,
                UserTable.is_approved == False
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def search_candidates(self, search_params: CandidateSearchSchema, limit: int = 20, offset: int = 0) -> List[
        UserTable]:
        """Search candidates with filters."""
        query = select(UserTable).where(
            and_(
                UserTable.role == UserRole.CANDIDATE,
                UserTable.is_active == True
            )
        )

        if search_params.role:
            query = query.where(UserTable.position.ilike(f"%{search_params.role}%"))

        if search_params.location:
            query = query.where(UserTable.location.ilike(f"%{search_params.location}%"))

        if search_params.experience_level:
            query = query.where(UserTable.experience_level == search_params.experience_level)

        if search_params.position:
            query = query.where(UserTable.position.ilike(f"%{search_params.position}%"))

        query = query.limit(limit).offset(offset)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def approve_team(self, team_id: int) -> Optional[UserTable]:
        """Approve a team."""
        # Get the actual database object, not the Pydantic model
        stmt = select(self._table).where(self._table.id == team_id)
        result = await self._db_session.execute(stmt)
        team = result.scalar_one_or_none()

        if team and team.role == UserRole.TEAM:
            team.is_approved = True
            await self._db_session.commit()
            await self._db_session.refresh(team)
            return team
        return None

    async def activate_user(self, user_id: int) -> Optional[UserTable]:
        """Activate a user."""
        # Get the actual database object, not the Pydantic model
        stmt = select(self._table).where(self._table.id == user_id)
        result = await self._db_session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            user.is_active = True
            await self._db_session.commit()
            await self._db_session.refresh(user)
            return user
        return None

    async def deactivate_user(self, user_id: int) -> Optional[UserTable]:
        """Deactivate a user."""
        # Get the actual database object, not the Pydantic model
        stmt = select(self._table).where(self._table.id == user_id)
        result = await self._db_session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            user.is_active = False
            await self._db_session.commit()
            await self._db_session.refresh(user)
            return user
        return None

    async def get_candidates_with_active_membership(self) -> List[UserTable]:
        """Get candidates with active membership."""
        query = select(UserTable).join(
            UserTable.memberships
        ).where(
            and_(
                UserTable.role == UserRole.CANDIDATE,
                UserTable.is_active == True,
                UserTable.memberships.any(status="active")
            )
        ).options(selectinload(UserTable.memberships))
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_all(self, limit: int, offset: int):
        stmt = select(UserTable).limit(limit).offset(offset)
        result = await self._db_session.execute(stmt)
        return result.scalars().all()

    async def count(self):
        stmt = select(func.count()).select_from(UserTable)
        result = await self._db_session.execute(stmt)
        return result.scalar_one()
