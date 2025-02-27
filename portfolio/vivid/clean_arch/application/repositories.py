from __future__ import annotations

from abc import ABC
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from clean_arch.domain.entities import (
    BaseEntityFilterModel,
    BaseEntityModel,
    EntityFilterModel,
    EntityModel,
    LimitOffset,
)

T_BaseEntity = TypeVar('T_BaseEntity', bound=BaseEntityModel)
T_BaseFilter = TypeVar('T_BaseFilter', bound=BaseEntityFilterModel)
T_Entity = TypeVar('T_Entity', bound=EntityModel)
T_Filter = TypeVar('T_Filter', bound=EntityFilterModel)


class BaseRORepo(ABC, Generic[T_BaseEntity, T_BaseFilter]):
    """Base Read Only Repository Mixin"""

    def get_filter_for_get_str(self, obj_id: str) -> T_BaseFilter:
        """To be used in get method when the obj_id is a string.
        Should be implemented in the child class
        """
        raise NotImplementedError

    async def get(self, obj_id: int | str | UUID) -> Optional[T_BaseEntity]:
        """Returns an entity from the repository or raises NotExists"""
        raise NotImplementedError

    async def list(self, page: LimitOffset, entity_filter: Optional[T_BaseFilter] = None) -> list[T_BaseEntity]:
        """Returns a list of entities from the repository"""
        raise NotImplementedError

    async def count(self, entity_filter: Optional[T_BaseFilter] = None) -> int:
        """Returns a number of entities from the repository"""
        raise NotImplementedError


class BaseWORepo(ABC, Generic[T_BaseEntity, T_BaseFilter]):
    """Base Write Only Repository Mixin"""

    async def add(self, entity: T_BaseEntity) -> T_BaseEntity:
        """Adds entity to the repository"""
        raise NotImplementedError

    async def update(
        self,
        entity: T_BaseEntity,
        entity_filter: Optional[T_BaseFilter] = None,
        model_dump: Optional[dict[str, Any]] = None,
    ) -> int:
        """Updates entity in the repository"""
        raise NotImplementedError

    async def update_by_filter(self, entity_filter: T_BaseFilter, values: dict[str, Any]) -> int:
        """Updates entities in the repository"""
        raise NotImplementedError

    async def remove(self, entity_filter: T_BaseFilter) -> int:
        """Removes specific entity from the repository"""
        raise NotImplementedError

    async def commit(self) -> None:
        """Commits write operations to the repository"""


_T_Repo = TypeVar('_T_Repo', bound='ContextManagerRepo')


class ContextManagerRepo:
    async def __aenter__(self: _T_Repo) -> _T_Repo:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass


class BaseRepo(ContextManagerRepo, BaseRORepo[T_BaseEntity, T_BaseFilter], BaseWORepo[T_BaseEntity, T_BaseFilter], ABC):
    """Base Repository"""
