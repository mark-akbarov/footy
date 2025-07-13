from typing import Optional, List, Type
from datetime import datetime

from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload, InstrumentedAttribute

from db.crud.base import BaseCrud
from db.tables.vacancy import Vacancy, VacancyStatus
from schemas.vacancy import CreateVacancySchema, UpdateVacancySchema, VacancySearchSchema, OutVacancySchema, PaginatedVacancySchema


class VacancyCrud(BaseCrud[CreateVacancySchema, UpdateVacancySchema, OutVacancySchema, PaginatedVacancySchema, Vacancy]):
    @property
    def _table(self) -> Type[Vacancy]:
        return Vacancy

    @property
    def _out_schema(self) -> Type[OutVacancySchema]:
        return OutVacancySchema

    @property
    def default_ordering(self) -> InstrumentedAttribute:
        return self._table.created_at.desc()

    @property
    def _paginated_schema(self) -> Type[PaginatedVacancySchema]:
        return PaginatedVacancySchema
    async def get_active_vacancies(self) -> List[Vacancy]:
        """Get all active vacancies."""
        query = select(Vacancy).where(
            and_(
                Vacancy.status == VacancyStatus.ACTIVE,
                Vacancy.expiry_date > datetime.utcnow()
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_vacancies_by_team_id(self, team_id: int) -> List[Vacancy]:
        """Get all vacancies for a team."""
        query = select(Vacancy).where(Vacancy.team_id == team_id)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def search_vacancies(self, search_params: VacancySearchSchema, limit: int = 20, offset: int = 0) -> List[Vacancy]:
        """Search vacancies with filters."""
        query = select(Vacancy).where(
            and_(
                Vacancy.status == VacancyStatus.ACTIVE,
                Vacancy.expiry_date > datetime.utcnow()
            )
        )
        
        if search_params.role:
            query = query.where(Vacancy.title.ilike(f"%{search_params.role}%"))
        
        if search_params.location:
            query = query.where(Vacancy.location.ilike(f"%{search_params.location}%"))
        
        if search_params.experience_level:
            query = query.where(Vacancy.experience_level == search_params.experience_level)
        
        if search_params.position_type:
            query = query.where(Vacancy.position_type == search_params.position_type)
        
        if search_params.salary_min:
            query = query.where(Vacancy.salary_min >= search_params.salary_min)
        
        if search_params.salary_max:
            query = query.where(Vacancy.salary_max <= search_params.salary_max)
        
        query = query.limit(limit).offset(offset)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_expired_vacancies(self) -> List[Vacancy]:
        """Get all expired vacancies."""
        query = select(Vacancy).where(
            and_(
                Vacancy.status == VacancyStatus.ACTIVE,
                Vacancy.expiry_date < datetime.utcnow()
            )
        )
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def close_vacancy(self, vacancy_id: int) -> Optional[Vacancy]:
        """Close a vacancy."""
        vacancy = await self.get_by_id(vacancy_id)
        if vacancy:
            vacancy.status = VacancyStatus.CLOSED
            await self._db_session.commit()
            await self._db_session.refresh(vacancy)
        return vacancy 