from typing import Type

from sqlalchemy.sql.elements import UnaryExpression

from db.crud.base import BaseCrud
from db.tables.user import User as UserTable
from schemas.user import (
    InUserSchema,
    UpdateUserSchema,
    OutUserSchema,
    PaginatedUsertSchema,
)


class UsersCrud(
    BaseCrud[
        InUserSchema,
        UpdateUserSchema,
        OutUserSchema,
        PaginatedUsertSchema,
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
    def _paginated_schema(self) -> Type[PaginatedUsertSchema]:
        return PaginatedUsertSchema
