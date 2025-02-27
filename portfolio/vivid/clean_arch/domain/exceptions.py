import http
from typing import Any


class DomainException(Exception):
    status_code: int = http.HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, msg: str, *args: Any, **kwargs: Any) -> None:
        field_exceptions: list[FieldException] = kwargs.pop('field_exceptions', [])
        super().__init__(msg.format(*args, **kwargs))
        self.raw_msg = msg
        self.raw_args = args
        self.raw_kwargs = kwargs
        self.field_exceptions = field_exceptions


class FieldException(DomainException):
    status_code: int = http.HTTPStatus.BAD_REQUEST

    def __init__(self, field: str, msg: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(msg, *args, **kwargs)
        self.field = field
