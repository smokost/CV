from abc import ABC, abstractmethod


class ExampleQuery(ABC):
    """Definition what exactly the query should do"""

    @abstractmethod
    async def execute(self) -> int:
        pass
