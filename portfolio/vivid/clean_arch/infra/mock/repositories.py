from __future__ import annotations

import asyncio
from copy import deepcopy
from itertools import count
from typing import Any, Dict, Generic, Optional, Type, TypeVar
from uuid import UUID

from clean_arch.application.repositories import BaseRepo, T_Entity, T_Filter
from clean_arch.domain.entities import LimitOffset
from clean_arch.domain.exceptions import DomainException
from clean_arch.utils.sort import multikeysort

_get_id = count(1).__next__


class BaseMockStore(Generic[T_Entity]):

    _lock: asyncio.Lock
    _mock_store: Dict[UUID, T_Entity]
    _store: Dict[UUID, T_Entity]
    _local_store: Dict[UUID, T_Entity]
    _local_removed_store: Dict[UUID, T_Entity]


_T = TypeVar('_T', bound=BaseMockStore[Any])


class MockGenericRepo(BaseMockStore[T_Entity], BaseRepo[T_Entity, T_Filter]):

    entity_cls: Type[T_Entity]
    filter_cls: Type[T_Filter]
    already_exists_err: Type[DomainException]

    def __init__(self, store: Optional[Dict[UUID, T_Entity]] = None) -> None:
        self._lock = asyncio.Lock()
        if store is None:
            self._store = self._mock_store
        else:
            self._store = store

    def apply_filter(
        self,
        item: T_Entity,
        entity_filter: T_Filter,
    ) -> bool:
        result = True
        excluded_keys = entity_filter.get_excluded_for_filter_keys()
        for field in entity_filter.model_fields_set:
            if field in excluded_keys:
                continue
            result &= getattr(item, field) == getattr(entity_filter, field)
            if not result:
                break
        return result

    def apply_order_by(
        self,
        items: list[T_Entity],
        entity_filter: Optional[T_Filter] = None,
    ) -> Any:
        if items and entity_filter and entity_filter.order_by is not None:
            items = multikeysort(items, entity_filter.order_by)
        return items

    async def get(self, obj_id: int | str | UUID) -> Optional[T_Entity]:
        if not isinstance(obj_id, (int, str, UUID)):
            raise ValueError(f'Unsupported obj_id type: {type(obj_id)}')

        if isinstance(obj_id, UUID):
            entity = self._local_store.get(obj_id) or self._store.get(obj_id)
        elif isinstance(obj_id, int):
            entity_filter = self.filter_cls(id=obj_id)
            entities = await self.list(LimitOffset(limit=1), entity_filter)
            entity = entities[0] if entities else None
        else:
            entity_filter = self.get_filter_for_get_str(obj_id)
            entities = await self.list(LimitOffset(limit=1), entity_filter)
            entity = entities[0] if entities else None
        if entity is None:
            return None
        return entity.model_copy(deep=True)

    async def list(self, page: LimitOffset, entity_filter: Optional[T_Filter] = None) -> list[T_Entity]:
        _store = {**self._store, **self._local_store}
        results = list(_store.values())
        if entity_filter is not None:
            results = [item for item in _store.values() if self.apply_filter(item, entity_filter)]

        if page.offset > 0:
            results = results[page.offset :]  # noqa: E203
        if page.limit > 0:
            results = results[: page.limit]
        return self.apply_order_by([item.model_copy(deep=True) for item in results], entity_filter)

    async def count(self, entity_filter: Optional[T_Filter] = None) -> int:
        _store = {**self._store, **self._local_store}
        if not entity_filter:
            return len(_store.values())
        cnt = 0
        for item in _store.values():
            if self.apply_filter(item, entity_filter):
                cnt += 1
        return cnt

    async def add(self, entity: T_Entity) -> T_Entity:
        entity.id = _get_id()
        if entity.uuid in self._local_store:
            raise self.already_exists_err(f'{self.entity_cls.__name__} already exists: {entity.uuid}')
        self._local_store[entity.uuid] = entity

        result = await self.get(entity.uuid)
        if result is None:
            raise LookupError(f'something wrong: {self.entity_cls.__name__} created but not found: {entity.id}')

        return result

    async def update(
        self, entity: T_Entity, entity_filter: Optional[T_Filter] = None, model_dump: Optional[dict[str, Any]] = None
    ) -> int:
        model_dump = model_dump or {'exclude': {'id', 'uuid'}}

        entity_filter = entity_filter or self.filter_cls()
        entities = await self.list(LimitOffset().inf, entity_filter.model_copy(update={'uuid': entity.uuid}))
        if not entities:
            return 0

        _store = {**self._store, **self._local_store}
        if entity.uuid not in _store:
            return 0

        self._local_store[entity.uuid] = _store[entity.uuid].model_copy(update=entity.model_dump(**model_dump))

        return 1

    async def update_by_filter(self, entity_filter: T_Filter, values: dict[str, Any]) -> int:
        entities = await self.list(LimitOffset().inf, entity_filter)
        _store = {**self._store, **self._local_store}

        for entity in entities:
            self._local_store[entity.uuid] = _store[entity.uuid].model_copy(update=values)

        return len(entities)

    async def remove(self, entity_filter: T_Filter) -> int:
        entities = await self.list(LimitOffset().inf, entity_filter)

        for entity in entities:
            self._local_removed_store[entity.uuid] = self._local_store.pop(entity.uuid)

        return len(entities)

    async def commit(self) -> None:
        self._store.update(self._local_store)
        for uuid in self._local_removed_store:
            self._store.pop(uuid)
        self._local_store = deepcopy(self._store)
        self._local_removed_store = {}
        await asyncio.sleep(0.001)  # simulating an async delay

    async def __aenter__(self: _T) -> _T:
        await self._lock.acquire()
        if hasattr(self, '_local_store'):
            raise RuntimeError('Already in a session')
        self._local_store: Dict[UUID, T_Entity] = deepcopy(self._store)
        self._local_removed_store: Dict[UUID, T_Entity] = {}
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            del self._local_store
            del self._local_removed_store
        finally:
            self._lock.release()
