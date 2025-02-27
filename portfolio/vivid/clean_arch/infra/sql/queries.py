from __future__ import annotations

import asyncio
from typing import Any, Callable, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from clean_arch.application.queries import ContextManagerQuery


class SQLQuery:  # noqa: SIM119
    def __init__(self, make_session: Callable[[], AsyncSession]):
        self._make_session = make_session


_T = TypeVar('_T', bound='SQLContextManagerQuery')


class SQLContextManagerQuery(SQLQuery, ContextManagerQuery):
    _session: AsyncSession
    _session_used: bool = False

    def __init__(self, make_session: Callable[[], AsyncSession]):
        super().__init__(make_session)
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
