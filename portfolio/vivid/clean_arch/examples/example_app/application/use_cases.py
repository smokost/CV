from uuid import UUID

from examples.example_app.application.repositories import ExampleRepo
from examples.example_app.domain.entities import ExampleEntity
from examples.example_app.domain.exceptions import ExampleEntityNotFound


class ExampleGetUseCase:
    def __init__(self, repo: ExampleRepo):
        self._repo = repo

    async def execute(self, uuid: UUID) -> ExampleEntity:
        async with self._repo:
            async with self._repo:
                entity = await self._repo.get(uuid)

            if not entity:
                raise ExampleEntityNotFound('Entity not found')

            return entity
