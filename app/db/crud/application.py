from typing import Optional, List, Type

from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload, InstrumentedAttribute

from db.crud.base import BaseCrud
from db.tables.application import Application, ApplicationStatus
from schemas.application import CreateApplicationSchema, UpdateApplicationSchema, OutApplicationSchema, PaginatedApplicationSchema


class ApplicationCrud(BaseCrud[CreateApplicationSchema, UpdateApplicationSchema, OutApplicationSchema, PaginatedApplicationSchema, Application]):
    @property
    def _table(self) -> Type[Application]:
        return Application

    @property
    def _out_schema(self) -> Type[OutApplicationSchema]:
        return OutApplicationSchema

    @property
    def default_ordering(self) -> InstrumentedAttribute:
        return self._table.created_at.desc()

    @property
    def _paginated_schema(self) -> Type[PaginatedApplicationSchema]:
        return PaginatedApplicationSchema
    async def get_applications_by_candidate_id(self, candidate_id: int) -> List[Application]:
        """Get all applications for a candidate."""
        query = select(Application).where(Application.candidate_id == candidate_id)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_applications_by_vacancy_id(self, vacancy_id: int) -> List[Application]:
        """Get all applications for a vacancy."""
        query = select(Application).where(Application.vacancy_id == vacancy_id)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_pending_applications_by_team(self, team_id: int) -> List[Application]:
        """Get all pending applications for a team's vacancies."""
        query = select(Application).join(
            Application.vacancy
        ).where(
            and_(
                Application.vacancy.has(team_id=team_id),
                Application.status == ApplicationStatus.PENDING
            )
        ).options(selectinload(Application.vacancy))
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def check_existing_application(self, candidate_id: int, vacancy_id: int) -> Optional[Application]:
        """Check if candidate already applied to this vacancy."""
        query = select(Application).where(
            and_(
                Application.candidate_id == candidate_id,
                Application.vacancy_id == vacancy_id
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def update_application_status(self, application_id: int, status: ApplicationStatus) -> Optional[Application]:
        """Update application status."""
        application = await self.get_by_id(application_id)
        if application:
            application.status = status
            await self._db_session.commit()
            await self._db_session.refresh(application)
        return application

    async def get_accepted_applications_by_candidate(self, candidate_id: int) -> List[Application]:
        """Get all accepted applications for a candidate."""
        query = select(Application).where(
            and_(
                Application.candidate_id == candidate_id,
                Application.status == ApplicationStatus.ACCEPTED
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().all() 