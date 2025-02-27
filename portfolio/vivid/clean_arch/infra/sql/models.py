import enum
from typing import Any, Type

from sqlalchemy import Enum


def sql_enum(tp: Type[enum.Enum], prefix: str, **kwargs: Any) -> Enum:
    return Enum(tp, name=prefix + '_' + tp.__name__.lower(), **kwargs)
