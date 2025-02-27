from sqlalchemy import select
from sqlalchemy.sql.functions import count

from clean_arch.infra.sql.queries import SQLQuery
from examples.example_app.application.queries import ExampleQuery
from examples.example_app.domain.value_objects import ExampleEntityStatus
from examples.example_app.infra.sql.models import SQLExampleEntity


class SQLExampleQuery(SQLQuery, ExampleQuery):
    async def execute(self) -> int:
        async with self._make_session() as session:
            query = select(count()).select_from(SQLExampleEntity).filter_by(status=ExampleEntityStatus.CREATED)
            result = await session.execute(query)
            return result.scalar()
