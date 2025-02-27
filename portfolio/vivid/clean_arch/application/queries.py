from typing import Any, TypeVar

_T_Query = TypeVar('_T_Query', bound='ContextManagerQuery')


class ContextManagerQuery:
    """Query with context manager support

    Essential for writable queries.
    """

    async def commit(self) -> None:
        """Commits the transaction"""
        raise NotImplementedError

    async def __aenter__(self: _T_Query) -> _T_Query:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass
