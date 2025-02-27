from typing import Optional

from clean_arch.domain.entities import EntityFilterModel, EntityModel


class ExampleEntity(EntityModel):
    value: str


class ExampleEntityFilter(EntityFilterModel):
    value: Optional[str] = None
