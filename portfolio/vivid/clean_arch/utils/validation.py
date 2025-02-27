"""
This module contains utils for validation of data of inbound requests and entities.
"""
from __future__ import annotations

from typing import Any, Callable, ClassVar, TypeVar

from pydantic import BaseModel

DataValidatorType = Callable[[Any, dict[Any, Any]], None]
_EVT = TypeVar('_EVT', bound=BaseModel)
EntityValidatorType = Callable[[_EVT, Any, dict[Any, Any]], None]


class EntityValidator:
    """A class for validation of data and entities.

    Can be mixed to pydantic models, or used as a standalone class.

    Example:
        def data_validator(obj: Any, ctx: dict[Any, Any]) -> None:
            if obj.name == 'John Doe':
                raise ValueError('Name cannot be John Doe')

        def entity_validator(entity: BaseModel, obj: Any, ctx: dict[Any, Any]) -> None:
            if entity.name != obj.name:
                raise ValueError('Name mismatch')

        validator = EntityValidator(
            data_validators=[data_validator],
            entity_validators=[entity_validator],
        )

        validator.validate_data(request.data, ctx)
        validator.validate_entity(entity, request.data, ctx)
    """

    data_validators: list[DataValidatorType] = []
    entity_validators: list[EntityValidatorType[Any]] = []

    def __init__(
        self,
        data_validators: list[DataValidatorType] | None = None,
        entity_validators: list[EntityValidatorType[Any]] | None = None,
    ) -> None:
        self.data_validators = list(self.data_validators)
        if data_validators:
            self.data_validators.extend(data_validators)
        self.entity_validators = list(self.entity_validators)
        if entity_validators:
            self.entity_validators.extend(entity_validators)

    def validate_data(self, obj: Any, ctx: dict[Any, Any]) -> None:
        for validator in self.data_validators:
            validator(obj, ctx)

    def validate_entity(self, entity: BaseModel, obj: Any, ctx: dict[Any, Any]) -> None:
        for validator in self.entity_validators:
            validator(entity, obj, ctx)


class ValidateEntityMixin:
    """Mixin to pydantic models for validation of data and entities using EntityValidator.

    Example:
        class UserAnswerRequest(ValidateEntityMixin, BaseModel):
            id: int
            text: str

            _validator = EntityValidator(
                data_validators=[answer_too_short, answer_too_long],
                entity_validators=[answer_status_not_created],
            )

        request = UserAnswerRequest(text='Hello')
        request.validate_data(ctx)
        entity = repo.get(request.id)
        request.validate_entity(entity, ctx)
    """

    _validator: ClassVar[EntityValidator]

    def validate_data(self, ctx: dict[Any, Any]) -> None:
        self._validator.validate_data(self, ctx)

    def validate_entity(self, entity: BaseModel, ctx: dict[Any, Any]) -> None:
        self._validator.validate_entity(entity, self, ctx)
