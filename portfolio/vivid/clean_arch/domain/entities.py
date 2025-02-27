from __future__ import annotations

from typing import Optional, Protocol, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

INF = -1

_T = TypeVar('_T', bound='SelectProtocol')


class SelectProtocol(Protocol):
    def limit(self: _T, limit: int) -> _T:
        ...

    def offset(self: _T, offset: int) -> _T:
        ...


class LimitOffset(BaseModel):
    limit: int = 20
    offset: int = 0

    def paginate(self, select: _T) -> _T:
        """Adds pagination to a query, e.g. sqlalchemy.sql.Select"""
        if self.limit > 0:
            select = select.limit(self.limit)
        if self.offset > 0:
            select = select.offset(self.offset)
        return select

    @property
    def inf(self) -> 'LimitOffset':
        return self.model_copy(update={'limit': INF})


class BaseEntityModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EntityModel(BaseEntityModel):
    id: Optional[int] = None
    uuid: UUID = Field(default_factory=uuid4)


class BaseEntityFilterModel(BaseModel):

    order_by: Optional[str] = None
    """Simple ordering of the items. Use comma separated values. Prefix with '-' for descending order.
    Example: 'name,-created_at'
    """

    @classmethod
    def get_excluded_for_filter_keys(cls) -> set[str]:
        """Returns a set of keys that should not be used for filtering"""
        return {'order_by'}


class EntityFilterModel(BaseEntityFilterModel):
    id: Optional[int] = None
    uuid: Optional[UUID] = None
