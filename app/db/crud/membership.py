from typing import Optional, Type
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload, InstrumentedAttribute

from db.crud.base import BaseCrud
from db.tables.membership import Membership, MembershipStatus
from schemas.membership import CreateMembershipSchema, UpdateMembershipSchema, OutMembershipSchema, \
    PaginatedMembershipSchema


class MembershipCrud(BaseCrud[
                         CreateMembershipSchema, UpdateMembershipSchema, OutMembershipSchema, PaginatedMembershipSchema, Membership]):
    @property
    def _table(self) -> Type[Membership]:
        return Membership

    @property
    def _out_schema(self) -> Type[OutMembershipSchema]:
        return OutMembershipSchema

    @property
    def default_ordering(self) -> InstrumentedAttribute:
        return self._table.created_at.desc()

    @property
    def _paginated_schema(self) -> Type[PaginatedMembershipSchema]:
        return PaginatedMembershipSchema

    async def get_active_membership_by_user_id(self, user_id: int) -> Optional[Membership]:
        """Get the active membership for a user."""
        query = select(Membership).where(
            and_(
                Membership.user_id == user_id,
                Membership.status == MembershipStatus.ACTIVE
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def get_memberships_by_user_id(self, user_id: int) -> list[Membership]:
        """Get all memberships for a user."""
        query = select(Membership).where(Membership.user_id == user_id)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_expired_memberships(self) -> list[Membership]:
        """Get all expired memberships."""
        query = select(Membership).where(
            and_(
                Membership.status == MembershipStatus.ACTIVE,
                Membership.renewal_date < datetime.utcnow()
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def update_membership_status(self, membership_id: int, status: MembershipStatus) -> Optional[Membership]:
        """Update membership status."""
        membership = await self.get_by_id(membership_id)
        if membership:
            membership.status = status
            await self._db_session.commit()
            await self._db_session.refresh(membership)
        return membership

    async def create_membership(self, membership_data: dict):
        """Create a new membership."""
        try:
            print("!!!!!! DEBUG: Data before creating membership:", membership_data)
            membership = Membership(**membership_data)
            self._db_session.add(membership)
            await self._db_session.commit()
            await self._db_session.refresh(membership)
            return "ok"
        except Exception as e:
            await self._db_session.rollback()
            print("!!!!! ERROR inserting membership:", e)
            raise
