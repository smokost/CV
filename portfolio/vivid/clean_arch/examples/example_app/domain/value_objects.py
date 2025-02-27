from enum import Enum


class ExampleEntityStatus(str, Enum):
    NONE = 'NONE'
    CREATED = 'CREATED'
    DELETED = 'DELETED'
