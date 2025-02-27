from clean_arch.application.repositories import BaseRepo
from examples.example_app.domain.entities import ExampleEntity, ExampleEntityFilter


class ExampleRepo(BaseRepo[ExampleEntity, ExampleEntityFilter]):
    async def count_something(self, entity: ExampleEntity) -> int:
        """App specific repo method for entity"""
        raise NotImplementedError
