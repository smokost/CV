from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.sql.functions import count

from clean_arch.domain.entities import LimitOffset
from clean_arch.infra.sql.repositories import SQLRepo
from examples.example_app.application.repositories import ExampleRepo
from examples.example_app.domain.entities import ExampleEntity, ExampleEntityFilter
from examples.example_app.domain.value_objects import ExampleEntityStatus
from examples.example_app.infra.sql.models import SQLExampleEntity


class SQLExampleRepo(SQLRepo, ExampleRepo):
    async def commit(self) -> None:
        await self._session.commit()

    async def count_something(self, entity: ExampleEntity) -> int:
        query = select(count()).select_from(SQLExampleEntity).filter_by(status=ExampleEntityStatus.DELETED)
        result = await self._session.scalar(query)
        return result or 0

    async def get(self, obj_id: int | str | UUID) -> Optional[ExampleEntity]:
        filter_by: dict[str, int | str | UUID] = {}
        if isinstance(obj_id, UUID):
            filter_by['uuid'] = obj_id
        elif isinstance(obj_id, int):
            filter_by['id'] = obj_id
        elif isinstance(obj_id, str):
            filter_by['uuid'] = UUID(obj_id)
        query = select(SQLExampleEntity).filter_by(**filter_by)
        result = await self._session.scalar(query)

        if result is None:
            return None

        return ExampleEntity.model_validate(result)

    async def list(self, page: LimitOffset, entity_filter: Optional[ExampleEntityFilter] = None) -> list[ExampleEntity]:
        query = page.paginate(select(SQLExampleEntity))

        if entity_filter:
            query = query.filter_by(**entity_filter.model_dump(exclude_unset=True))

        results = await self._session.scalars(query)
        return [ExampleEntity.model_validate(item) for item in results.fetchall()]

    async def count(self, entity_filter: Optional[ExampleEntityFilter] = None) -> int:
        query = select(count()).select_from(SQLExampleEntity)

        if entity_filter:
            query = query.filter_by(**entity_filter.model_dump(exclude_unset=True))

        return await self._session.scalar(query) or 0

    async def add(self, entity: ExampleEntity) -> ExampleEntity:
        data = entity.model_dump()
        sql_entity = SQLExampleEntity(**data)
        self._session.add(sql_entity)
        await self._session.flush()
        return ExampleEntity.model_validate(sql_entity)

    async def update(
        self,
        entity: ExampleEntity,
        entity_filter: Optional[ExampleEntityFilter] = None,
        model_dump: Optional[dict[str, Any]] = None,
    ) -> int:
        model_dump = model_dump or {'exclude': {'id', 'uuid'}}
        filter_by = {'uuid': entity.uuid}
        if entity_filter:
            filter_by.update(entity_filter.model_dump(exclude_unset=True))
        query = update(SQLExampleEntity).filter_by(**filter_by).values(**entity.model_dump(**model_dump))
        result = await self._session.execute(query)
        assert isinstance(result, CursorResult)
        return result.rowcount or 0

    async def remove(self, entity_filter: ExampleEntityFilter) -> int:
        query = delete(SQLExampleEntity).filter_by(**entity_filter.model_dump(exclude_unset=True))
        result = await self._session.execute(query)
        assert isinstance(result, CursorResult)
        return result.rowcount or 0
