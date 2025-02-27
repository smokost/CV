from uuid import UUID as PY_UUID
from uuid import uuid4

from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from clean_arch.domain.value_objects import Lang
from clean_arch.infra.sql.models import sql_enum
from examples.example_app.domain.value_objects import ExampleEntityStatus


class Base(AsyncAttrs, DeclarativeBase):
    pass


class SQLExampleEntity(Base):
    __tablename__ = 'example_entities'

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    uuid: Mapped[PY_UUID] = mapped_column(UUID(as_uuid=True), default=uuid4, index=True, unique=True)
    status: Mapped[ExampleEntityStatus] = mapped_column(
        sql_enum(ExampleEntityStatus, __tablename__), default=ExampleEntityStatus.NONE
    )
    lang: Mapped[Lang] = mapped_column(sql_enum(Lang, __tablename__), default=Lang.EN)
