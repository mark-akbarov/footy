from typing import Optional, List, Type, Any, Coroutine
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload, InstrumentedAttribute, joinedload

from db.crud.base import BaseCrud
from db.tables.vacancy import Vacancy, VacancyStatus
from schemas.vacancy import CreateVacancySchema, UpdateVacancySchema, VacancySearchSchema, OutVacancySchema, \
    PaginatedVacancySchema


class VacancyCrud(
    BaseCrud[CreateVacancySchema, UpdateVacancySchema, OutVacancySchema, PaginatedVacancySchema, Vacancy]):
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

    async def get_active_vacancies(self, team_id: int) -> List[Vacancy]:
        """Get all active vacancies for a specific team."""
        query = select(Vacancy).where(
            and_(
                Vacancy.status == VacancyStatus.ACTIVE,
                Vacancy.team_id == team_id,
                Vacancy.deleted_at.is_(None)  # Exclude soft-deleted vacancies
            )
        )
        print(f"Executing query: {query}")
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def get_vacancies_by_team_id(self, team_id: int) -> List[Vacancy]:
        """Get all vacancies for a team."""
        query = select(Vacancy).where(Vacancy.team_id == team_id)
        result = await self._db_session.execute(query)
        return result.scalars().all()

    async def search_vacancies(self, params: VacancySearchSchema, limit: int, offset: int):
        query = select(Vacancy).where(Vacancy.deleted_at.is_(None))  # Example filter

        if params.role:
            query = query.where(Vacancy.role.ilike(f"%{params.role}%"))
        if params.location:
            query = query.where(Vacancy.location.ilike(f"%{params.location}%"))
        if params.salary_min:
            query = query.where(Vacancy.salary_min >= params.salary_min)
        if params.salary_max:
            query = query.where(Vacancy.salary_max <= params.salary_max)
        if params.experience_level:
            query = query.where(Vacancy.experience_level.ilike(f"%{params.experience_level}%"))
        if params.position_type:
            query = query.where(Vacancy.position_type.ilike(f"%{params.position_type}%"))

        # Print query to debug
        print(str(query))

        result = await self._db_session.execute(query.limit(limit).offset(offset))
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

    async def close_vacancy(self, vacancy_id: int) -> OutVacancySchema:
        """Close a vacancy."""
        # Fetch the ORM model
        vacancy = await self._db_session.get(Vacancy, vacancy_id)

        if not vacancy:
            raise HTTPException(
                status_code=404, detail="Vacancy not found"
            )

        # Update the status
        vacancy.status = VacancyStatus.CLOSED

        # Commit and refresh to reload the updated instance
        await self._db_session.commit()
        await self._db_session.refresh(vacancy)

        # Convert the ORM model to a Pydantic schema
        return OutVacancySchema.model_validate(vacancy)

    async def create_vacancy(self, in_schema: CreateVacancySchema, team_id: int) -> Vacancy:
        """Create a new vacancy associated with a team."""
        vacancy = self._table(**in_schema.model_dump(), team_id=team_id)
        self._db_session.add(vacancy)
        await self._db_session.commit()
        await self._db_session.refresh(vacancy)
        return vacancy

    async def get_by_id_model(self, entry_id: int) -> Optional[Vacancy]:
        """Get a vacancy model instance by its ID."""
        query = select(self._table).options(joinedload(self._table.team)).where(self._table.id == entry_id)
        result = await self._db_session.execute(query)
        return result.scalars().first()

    async def update(
        self, obj_id: int, schema: UpdateVacancySchema, author_id: int
    ) -> Optional[Vacancy]:
        """Update a vacancy by its ID, with an authorization check."""
        # Retrieve the SQLAlchemy model instance
        vacancy_to_update = await self.get_by_id_model(obj_id)

        if not vacancy_to_update:
            return None  # Vacancy not found

        # Authorization check: only the author can update
        if vacancy_to_update.team_id != author_id:
            # For better security, you might want to raise a 403 Forbidden HTTPException here
            return None

        # Update the model with data from the schema
        update_data = schema.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(vacancy_to_update, field, value)

        await self._db_session.commit()
        await self._db_session.refresh(vacancy_to_update)

        return vacancy_to_update
