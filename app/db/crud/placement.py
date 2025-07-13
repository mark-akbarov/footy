from typing import Optional, List, Type

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload, InstrumentedAttribute

from db.crud.base import BaseCrud
from db.tables.placement import Placement, PlacementStatus
from schemas.placement import CreatePlacementSchema, UpdatePlacementSchema, OutPlacementSchema, PaginatedPlacementSchema


class PlacementCrud(BaseCrud[CreatePlacementSchema, UpdatePlacementSchema, OutPlacementSchema, PaginatedPlacementSchema, Placement]):
    @property
    def _table(self) -> Type[Placement]:
        return Placement

    @property
    def _out_schema(self) -> Type[OutPlacementSchema]:
        return OutPlacementSchema

    @property
    def default_ordering(self) -> InstrumentedAttribute:
        return self._table.created_at.desc()

    @property
    def _paginated_schema(self) -> Type[PaginatedPlacementSchema]:
        return PaginatedPlacementSchema
    async def get_placements_by_team_id(self, team_id: int) -> List[Placement]:
        """Get all placements for a team."""
        query = select(Placement).where(Placement.team_id == team_id)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_placements_by_candidate_id(self, candidate_id: int) -> List[Placement]:
        """Get all placements for a candidate."""
        query = select(Placement).where(Placement.candidate_id == candidate_id)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_unpaid_placements_by_team(self, team_id: int) -> List[Placement]:
        """Get all unpaid placements for a team."""
        query = select(Placement).where(
            and_(
                Placement.team_id == team_id,
                Placement.invoice_generated == True,
                Placement.invoice_paid == False
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_placement_by_application_id(self, application_id: int) -> Optional[Placement]:
        """Get placement by application ID."""
        query = select(Placement).where(Placement.application_id == application_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def confirm_placement(self, placement_id: int) -> Optional[Placement]:
        """Confirm a placement."""
        placement = await self.get_by_id(placement_id)
        if placement:
            placement.status = PlacementStatus.CONFIRMED
            await self._db_session.commit()
            await self._db_session.refresh(placement)
        return placement

    async def mark_invoice_generated(self, placement_id: int, pdf_path: str) -> Optional[Placement]:
        """Mark invoice as generated."""
        placement = await self.get_by_id(placement_id)
        if placement:
            placement.invoice_generated = True
            placement.invoice_pdf_path = pdf_path
            await self._db_session.commit()
            await self._db_session.refresh(placement)
        return placement

    async def mark_invoice_paid(self, placement_id: int) -> Optional[Placement]:
        """Mark invoice as paid."""
        placement = await self.get_by_id(placement_id)
        if placement:
            placement.invoice_paid = True
            placement.status = PlacementStatus.COMPLETED
            await self._db_session.commit()
            await self._db_session.refresh(placement)
        return placement

    async def get_pending_invoices(self) -> List[Placement]:
        """Get all placements with pending invoice generation."""
        query = select(Placement).where(
            and_(
                Placement.status == PlacementStatus.CONFIRMED,
                Placement.invoice_generated == False
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().all() 