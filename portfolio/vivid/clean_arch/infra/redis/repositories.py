from __future__ import annotations

import asyncio
import json
from typing import Any, Optional, Type, TypeVar
from uuid import UUID

from redis.asyncio.client import Pipeline, Redis

from clean_arch.application.repositories import BaseRepo, ContextManagerRepo, T_Entity, T_Filter
from clean_arch.domain.entities import LimitOffset
from clean_arch.domain.exceptions import DomainException
from clean_arch.utils.sort import multikeysort

_T = TypeVar('_T', bound='RedisRepo')


class RedisRepo(ContextManagerRepo):
    _client: Redis
    _pipeline: Pipeline

    def __init__(self, client: Redis, prefix: str = '', ttl: Optional[int] = None):
        self._client = client
        self._lock = asyncio.Lock()
        self._prefix = prefix or self.__class__.__name__
        self._ttl = ttl

    async def commit(self) -> None:
        await self._pipeline.execute()

    async def _get_id(self) -> int:
        async with self._client.lock(f'{self._prefix}:id:lock', timeout=5):
            return await self._client.incr(f'{self._prefix}:id', amount=1)

    async def __aenter__(self: _T) -> _T:
        await self._lock.acquire()
        if hasattr(self, '_pipeline'):
            raise RuntimeError('Already in a session')
        self._pipeline = self._client.pipeline()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            await self._pipeline.__aexit__(exc_type, exc, tb)
            del self._pipeline
        finally:
            self._lock.release()


class RedisGenericSimpleRepo(RedisRepo, BaseRepo[T_Entity, T_Filter]):
    """Implementation of a generic repository for Redis that uses only simple commands.
    This implementation lacks of integrity compared to SQL."""

    entity_cls: Type[T_Entity]
    filter_cls: Type[T_Filter]
    already_exists_err: Type[DomainException]

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

    def on_add(self, entity: T_Entity) -> dict[Any, Any]:
        return entity.model_dump(mode='json')

    async def model_validate(self, data: str | dict[Any, Any]) -> T_Entity:
        if isinstance(data, (str, bytes)):
            data = json.loads(data)
        return self.entity_cls.model_validate(data)

    async def models_validate(self, datas: list[dict[Any, Any]]) -> list[T_Entity]:
        return [await self.model_validate(data) for data in datas]

    async def get_update_values(self, entity: T_Entity, model_dump: dict[str, Any]) -> dict[str, Any]:
        model_dump.setdefault('mode', 'json')
        return entity.model_dump(**model_dump)

    async def get(self, obj_id: int | str | UUID) -> Optional[T_Entity]:
        if not isinstance(obj_id, (str, int, UUID)):
            raise ValueError(f'Unsupported obj_id type: {type(obj_id)}')

        if isinstance(obj_id, int) and (value := await self._client.get(f'{self._prefix}:{obj_id}:uuid')):
            obj_id = value.decode()

        obj_id = str(obj_id)
        data = await self._client.get(f'{self._prefix}:{obj_id}')
        if not data:
            return None

        return await self.model_validate(data)

    async def list(self, page: LimitOffset, entity_filter: Optional[T_Filter] = None) -> list[T_Entity]:

        results: list[T_Entity] = []
        keys = [key async for key in self._client.scan_iter(match=f'{self._prefix}:*')]
        for key in keys:
            await self._pipeline.get(key)

        items = await self._pipeline.execute()
        i = -1
        for item in items:
            if item is None:
                continue

            item = await self.model_validate(item)
            if entity_filter is not None and not self.apply_filter(item, entity_filter):
                continue
            i += 1
            if page.offset > 0 and page.offset > i:
                continue
            results.append(item)
            if 0 < page.limit < len(results):
                break

        return self.apply_order_by(results, entity_filter)

    async def count(self, entity_filter: Optional[T_Filter] = None) -> int:
        if entity_filter is None:
            keys = [key async for key in self._client.scan_iter(match=f'{self._prefix}:*')]
            return len(keys)
        return len(await self.list(LimitOffset().inf, entity_filter))

    async def add(self, entity: T_Entity) -> T_Entity:

        data = self.on_add(entity)
        obj_id = await self._get_id()
        data['id'] = obj_id

        result = await self._client.set(f'{self._prefix}:{entity.uuid}', json.dumps(data), ex=self._ttl, nx=True)
        if not result:
            raise self.already_exists_err(f'{self.entity_cls.__name__} already exists: {entity.uuid}')
        await self._client.set(f'{self._prefix}:{obj_id}:uuid', str(entity.uuid).encode(), ex=self._ttl)
        entity.id = obj_id

        return entity

    async def update(
        self,
        entity: T_Entity,
        entity_filter: Optional[T_Filter] = None,
        model_dump: Optional[dict[str, Any]] = None,
    ) -> int:
        item = await self.get(entity.uuid)
        if item is None or entity_filter is not None and not self.apply_filter(item, entity_filter):
            return 0

        model_dump = model_dump or {}
        data = await self.get_update_values(entity, model_dump)
        result = await self._client.set(f'{self._prefix}:{entity.uuid}', json.dumps(data), ex=self._ttl, xx=True)
        return 1 if result else 0

    async def update_by_filter(self, entity_filter: T_Filter, values: dict[str, Any]) -> int:
        entities = await self.list(LimitOffset().inf, entity_filter)

        for entity in entities:
            entity = entity.model_copy(update=values)
            data = await self.get_update_values(entity, {})
            await self._pipeline.set(f'{self._prefix}:{entity.uuid}', json.dumps(data), ex=self._ttl, xx=True)

        result = await self._pipeline.execute()

        return sum(result)
