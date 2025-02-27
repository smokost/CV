import http

from clean_arch.domain.exceptions import DomainException


class ExampleEntityNotFound(DomainException):
    status_code = http.HTTPStatus.NOT_FOUND
