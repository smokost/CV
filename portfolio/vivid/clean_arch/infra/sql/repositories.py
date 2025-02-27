from __future__ import annotations

import asyncio
from typing import Any, Callable, Generic, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import CursorResult, Delete, Select, Update, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count

from clean_arch.application.repositories import BaseRepo, ContextManagerRepo, T_Entity, T_Filter
from clean_arch.domain.entities import LimitOffset
from clean_arch.domain.exceptions import DomainException
from clean_arch.infra.sql.utils import parse_order_by_string

_T = TypeVar('_T', bound='SQLRepo')


class SQLRepo(ContextManagerRepo):
    _session: AsyncSession

    def __init__(self, make_session: Callable[[], AsyncSession]):
        self._make_session = make_session
        self._lock = asyncio.Lock()

    async def commit(self) -> None:
        await self._session.commit()

    async def __aenter__(self: _T) -> _T:
        await self._lock.acquire()
        if hasattr(self, '_session'):
            raise RuntimeError('Already in a session')
        self._session = await self._make_session().__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            await self._session.__aexit__(exc_type, exc, tb)
            del self._session
        finally:
            self._lock.release()


T_SQL_Entity = TypeVar('T_SQL_Entity')


class SQLGenericRepo(Generic[T_SQL_Entity, T_Entity, T_Filter], SQLRepo, BaseRepo[T_Entity, T_Filter]):
    """Generic Repo for SQL databases

    The model should have fields 'id' and 'uuid'

    example:
        class Base(AsyncAttrs, DeclarativeBase):
            pass

        class SQLExampleEntity(Base):
            __tablename__ = 'example_entities'

            id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
            uuid: Mapped[PY_UUID] = mapped_column(UUID(as_uuid=True), default=uuid4, index=True, unique=True)
            status: Mapped[ExampleEntityStatus] = mapped_column(
                sql_enum(ExampleEntityStatus, __tablename__), default=ExampleEntityStatus.NONE
            )
            lang: Mapped[Lang] = mapped_column(sql_enum(Lang, __tablename__), default=Lang.EN)

    """

    sql_entity_cls: Type[T_SQL_Entity]
    entity_cls: Type[T_Entity]
    filter_cls: Type[T_Filter]
    already_exists_err: Type[DomainException]

    def apply_filter(
        self,
        query: Select[tuple[T_SQL_Entity]] | Select[tuple[int]] | Update | Delete,
        entity_filter: Optional[T_Filter] = None,
    ) -> Any:
        if entity_filter:
            return query.filter_by(
                **entity_filter.model_dump(exclude=entity_filter.get_excluded_for_filter_keys(), exclude_unset=True)
            )
        return query

    def apply_order_by(
        self,
        query: Select[tuple[T_SQL_Entity]] | Select[tuple[int]] | Update | Delete,
        entity_filter: Optional[T_Filter] = None,
    ) -> Any:
        if isinstance(query, Select) and entity_filter and entity_filter.order_by is not None:
            query = query.order_by(*parse_order_by_string(entity_filter.order_by))
        return query

    def on_add(self, entity: T_Entity) -> T_SQL_Entity:
        data = entity.model_dump(exclude={'id'})
        return self.sql_entity_cls(**data)

    async def model_validate(self, sql_entity: T_SQL_Entity) -> T_Entity:
        return self.entity_cls.model_validate(sql_entity)

    async def models_validate(self, sql_entities: list[T_SQL_Entity]) -> list[T_Entity]:
        return [await self.model_validate(sql_entity) for sql_entity in sql_entities]

    async def get_update_values(self, entity: T_Entity, model_dump: dict[str, Any]) -> dict[str, Any]:
        return entity.model_dump(**model_dump)

    async def get(self, obj_id: int | str | UUID) -> Optional[T_Entity]:
        if not isinstance(obj_id, (int, str, UUID)):
            raise ValueError(f'Unsupported obj_id type: {type(obj_id)}')

        if isinstance(obj_id, UUID):
            entity_filter = self.filter_cls(uuid=obj_id)
        elif isinstance(obj_id, int):
            entity_filter = self.filter_cls(id=obj_id)
        else:
            entity_filter = self.get_filter_for_get_str(obj_id)

        query = select(self.sql_entity_cls)
        query = self.apply_filter(query, entity_filter)
        query = self.apply_order_by(query, entity_filter)

        sql_entity = await self._session.scalar(query)
        return (await self.model_validate(sql_entity)) if sql_entity else None

    async def list(self, page: LimitOffset, entity_filter: Optional[T_Filter] = None) -> list[T_Entity]:
        query = page.paginate(select(self.sql_entity_cls))
        query = self.apply_filter(query, entity_filter)
        query = self.apply_order_by(query, entity_filter)

        sql_entities = await self._session.scalars(query)

        return await self.models_validate(list(sql_entities))

    async def count(self, entity_filter: Optional[T_Filter] = None) -> int:
        query = select(count()).select_from(self.sql_entity_cls)
        query = self.apply_filter(query, entity_filter)
        return await self._session.scalar(query) or 0

    async def add(self, entity: T_Entity) -> T_Entity:

        sql_entity = self.on_add(entity)

        self._session.add(sql_entity)

        try:
            await self._session.flush()
        except IntegrityError as err:
            if 'duplicate key value violates unique constraint' in str(
                err
            ) or 'asyncpg.exceptions.UniqueViolationError' in str(err.orig):
                raise self.already_exists_err(
                    f'{self.entity_cls.__name__} already exists: {getattr(sql_entity, "uuid")}'
                ) from err
            raise

        new_entity = await self.get(getattr(sql_entity, 'id'))
        if new_entity is None:
            raise LookupError(
                f'something wrong: {self.entity_cls.__name__} created but not found: {getattr(sql_entity, "id")}'
            )
        return new_entity

    async def update(
        self,
        entity: T_Entity,
        entity_filter: Optional[T_Filter] = None,
        model_dump: Optional[dict[str, Any]] = None,
    ) -> int:
        model_dump = model_dump or {'exclude': {'id', 'uuid'}}
        query = update(self.sql_entity_cls).filter_by(uuid=entity.uuid)
        query = self.apply_filter(query, entity_filter).values(**(await self.get_update_values(entity, model_dump)))
        result = await self._session.execute(query)
        assert isinstance(result, CursorResult)
        return result.rowcount or 0

    async def update_by_filter(self, entity_filter: T_Filter, values: dict[str, Any]) -> int:
        query = update(self.sql_entity_cls)
        query = self.apply_filter(query, entity_filter).values(**values)
        result = await self._session.execute(query)
        assert isinstance(result, CursorResult)
        return result.rowcount or 0

    async def remove(self, entity_filter: T_Filter) -> int:
        query = delete(self.sql_entity_cls)
        query = self.apply_filter(query, entity_filter)
        result = await self._session.execute(query)
        assert isinstance(result, CursorResult)
        return result.rowcount or 0
