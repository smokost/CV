import asyncio
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from itertools import chain
from logging import getLogger
from typing import Type, TypedDict

from bson import ObjectId
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from pymongo import ReplaceOne, UpdateOne

from collector.services.images import choose_s3_bucket, upload_activity_media_to_s3
from project.db.models.activities import Activity, ActivityCategory, ActivityManager, ActivityMedia
from project.db.models.activities.common import (
    ActivityBudget,
    ActivityCommonFields,
    ActivityDate,
    ActivityDestination,
    ActivityRating,
)
from project.db.models.base import BaseModelManager, Model, PyObjectId
from project.db.models.providers import DataProvider
from project.utils.state import State
from project.utils.strings import slugify
from project.utils.timezones import now_utc

logger = getLogger(__name__)


class BaseCollector(ABC):
    """Базовый коллектор объектов"""

    def __init__(self, page_size: int):
        self.page_size = page_size
        self.is_stopped = False
        self.cycles = 0
        self.objects_total = 0

    async def run(self) -> None:
        """Запуск основного цикла сбора событий"""
        logger.info('Start to collect')

        while not self.is_stopped:
            self.cycles += 1
            logger.info('Start collection cycle %s', self.cycles)
            objects_count = await self.collect()
            self.objects_total += objects_count
            logger.info(
                'Finish collection cycle %s. Objects: %s. Objects total: %s',
                self.cycles,
                objects_count,
                self.objects_total,
            )

        logger.info('Collecting finished. Cycles: %s. Objects total: %s', self.cycles, self.objects_total)

    def stop(self) -> None:
        self.is_stopped = True

    @abstractmethod
    async def collect(self) -> int:
        """Одна итерация сбора объектов"""


class BaseDefinedPagesCollector(BaseCollector, ABC):
    """Коллектор, с подготовленным методом .collect() с постраничным принципом загрузки"""

    _min_page_number: int = 0
    _max_page_number: int = 1000000000
    _max_tasks: int = 5

    async def collect(self) -> int:
        """Одна итерация сбора объектов"""
        if self._min_page_number > self._max_page_number:
            logger.info('No pages to process. Stopping')
            self.stop()
            return 0

        tasks = []
        from_page = self._min_page_number
        to_page = min(self._min_page_number + self._max_tasks, self._max_page_number + 1)
        for page_number in range(from_page, to_page):
            task = asyncio.create_task(self.process_page(page_number))
            tasks.append(task)
            self._min_page_number = max(self._min_page_number, page_number + 1)

        page_datas = await asyncio.gather(*tasks)

        return len(list(chain.from_iterable(page_datas)))

    @abstractmethod
    async def process_page(self, page_number: int) -> list:
        """Загрузка и обработка одной страницы с заданным номером"""


class UpsertMixin:
    """Mixin for Mongodb ReplaceOne or UpdateOne operations"""

    def __init__(self, *args, **kwargs) -> None:
        kwargs['upsert'] = True
        super().__init__(*args, **kwargs)


class ReplaceOneUpsert(UpsertMixin, ReplaceOne):
    """Mongodb ReplaceOne operation with upsert=True"""


class UpdateOneUpsert(UpsertMixin, UpdateOne):
    """Mongodb UpdateOne operation with upsert=True"""


class BaseUploader(ABC):
    """Базовый загрузчик объектов, полученных при работе коллектора"""

    manager_cls: Type[BaseModelManager]
    request_cls: Type[object] = ReplaceOneUpsert

    raise_exception: bool = True

    async def upload(self, data: list[dict]) -> None:
        """Загружает объекты в БД.

        Для каждого объекта формирует экземпляр модели, проверяет его валидность
        (наличие необходимых полей для идентификации), формирует фильтр для поиска
        такого документа в БД, формирует запрос для сохранения. Использует bulk_write
        для сохранения объектов пачкой.
        """
        bulk_write = []
        errors = []
        for item in data:
            try:
                instance = await self.get_instance(item)
                instance.is_valid = bool(self.is_valid(instance))
                document_filter = self.get_document_filter(instance)
                document_data = self.get_document_data(instance)
                request = self.request_cls(document_filter, document_data)
                bulk_write.append(request)
            except Exception as err:
                if not self.raise_exception:
                    errors.append(traceback.format_exc())
                    continue
                logger.error('Raised error for item %s', item)
                raise err

        if bulk_write:
            logger.debug('Bulk write of %s elements', len(bulk_write))
            await self.manager_cls().collection.bulk_write(bulk_write)
        else:
            logger.debug('No data to write')

        if errors:
            logger.error(
                'Got %s errors during uploading of activities by %s. One of errors is: `%s`',
                len(errors),
                self.__class__.__name__,
                errors[0],
            )
        for error in errors:
            logger.debug('%s error: %s', self.__class__.__name__, error)

    @abstractmethod
    async def get_instance(self, item: dict) -> Model:
        """Возвращает экземпляр модели"""

    def is_valid(self, instance: Model) -> bool:
        """Проверяет валидность полученных данных.

        В этом методе можно проверить заполненность обязательных полей, таких как id,
        name, title, и других.

        Возвращает результат валидации. Если валидация не проходит, то это значение будет
        присвоено объекту в атрибут is_valid.
        """
        # pylint: disable=unused-argument
        return True

    @abstractmethod
    def get_document_filter(self, instance: Model) -> dict:
        """Возвращает фильтр в виде словаря для идентификации объекта в БД,
        если он уже когда-то был создан
        """
        return {'id': instance.id}

    def get_document_data(self, instance: Model) -> dict:
        """Возвращает данные в виде словаря, которые будут сохранены в БД"""
        return jsonable_encoder(instance, exclude={'id'})


class BaseActivitiesUploader(BaseUploader, ABC):
    """Базовый загрузчик событий, полученных при работе коллектора событий"""

    manager_cls: Type[ActivityManager] = ActivityManager
    request_cls: Type[object] = UpdateOneUpsert
    provider: DataProvider
    mapper_cls: Type['AbstractActivityMapper']

    def __init__(self, filter_features: BaseModel, category: ActivityCategory = ActivityCategory.EVENT):
        self.filter_features = filter_features
        self.category = category

    async def get_instance(self, item) -> Activity:
        mapper = self.mapper_cls(item, self)
        instance = Activity(
            provider=self.provider,
            filter_features=self.filter_features.dict(exclude_none=True),
            content=item,
            category=mapper.category,
            subcategory=mapper.subcategory,
            common_fields=ActivityCommonFields(
                title=mapper.title,
                external_url=mapper.external_url,
                description=mapper.description,
                media=[],  # Загружается чуть позже, если manually_modified=False
                tags=mapper.tags,
                destinations=mapper.destinations,
                budgets=mapper.budgets,
                dates=mapper.dates,
                ratings=mapper.ratings,
            ),
            secondary_contents={},
            special_fields={self.provider: mapper.special_fields},
            obsolete=False,
            updated_at=now_utc(),
        )
        document_filter = self.get_document_filter(instance)
        document = await self.manager_cls().collection.find_one(document_filter)
        should_upload_media = True
        if document:
            logger.debug('Got real document by filter %s', document_filter)
            real_instance = Activity.parse_obj(document)
            if real_instance.manually_modified:
                should_upload_media = False
            else:
                real_instance.filter_features = instance.filter_features
                real_instance.content = instance.content
                real_instance.category = instance.category
                real_instance.common_fields = instance.common_fields
                real_instance.special_fields.update(instance.special_fields)
            real_instance.updated_at = instance.updated_at
            instance = real_instance

        if should_upload_media:
            s3_bucket = choose_s3_bucket(self.provider, self.filter_features, mapper.destinations)
            media = await upload_activity_media_to_s3(mapper.media, s3_bucket, suffix=slugify(mapper.title))
            instance.common_fields.media = media

        return instance

    def get_document_filter(self, instance: Activity) -> dict:
        """Фильтр подходит для большинства провайдеров. В особых случаях метод нужно переопределить."""
        return {
            'provider': self.provider.value,
            'content.id': instance.content['id'],
        }

    def get_document_data(self, instance: Activity) -> dict:
        """Возвращает данные для обновления или создания нового документа"""
        exclude = {
            'id',
            'common_fields',
            'secondary_contents',
            'special_fields',
            'activity_group_id',
            'duplicate_of',
            'master_of',
            'manually_modified',
            'aola_choice',
        }
        data = jsonable_encoder(instance, exclude=exclude, custom_encoder={datetime: lambda x: x})

        common_fields: dict = jsonable_encoder(instance.common_fields, exclude={'gpt_description'})
        for key, value in common_fields.items():
            data[f'common_fields.{key}'] = value

        special_fields: dict = jsonable_encoder(instance.special_fields[self.provider])
        for key, value in special_fields.items():
            data[f'special_fields.{self.provider}.{key}'] = value

        return {'$set': data}

    def is_valid(self, instance: Activity) -> bool:
        """Проверяет валидность полученных данных"""
        if instance.manually_modified:
            return instance.is_valid

        return (
            bool(instance.common_fields.media)
            and bool(instance.common_fields.destinations)
            and not instance.category == ActivityCategory.EVENT
            and not instance.duplicate_of
        )


class AbstractActivityMapper(ABC):
    """Abstract Event Mapper"""

    def __init__(self, item: dict, uploader: BaseActivitiesUploader):
        self.item = item
        self.uploader = uploader

    @property
    def category(self) -> ActivityCategory:
        return self.uploader.category

    @property
    def subcategory(self) -> str:
        return ''

    @property
    @abstractmethod
    def title(self) -> str:
        return ''

    @property
    @abstractmethod
    def external_url(self) -> str:
        return ''

    @property
    @abstractmethod
    def description(self) -> str:
        return ''

    @property
    @abstractmethod
    def media(self) -> list[ActivityMedia]:
        return []

    @property
    @abstractmethod
    def tags(self) -> list[str]:
        return []

    @property
    @abstractmethod
    def destinations(self) -> list[ActivityDestination]:
        return []

    @property
    @abstractmethod
    def budgets(self) -> list[ActivityBudget]:
        return []

    @property
    @abstractmethod
    def dates(self) -> list[ActivityDate]:
        return []

    @property
    @abstractmethod
    def ratings(self) -> list[ActivityRating]:
        return []

    @property
    @abstractmethod
    def special_fields(self) -> dict:
        return {}


class StateData(BaseModel):
    """State Data"""

    last_id: PyObjectId = ObjectId.from_datetime(datetime(2000, 1, 1))
    activities_count: int = 0
    activities_remaining: int = 0

    class Config:
        """Config"""

        json_encoders = {ObjectId: str}


class BaseActivitiesSpecificFieldsCollector:
    """Коллектор особых полей активностей, который отдельно от основного
    коллектора подгружает дополнительные данные в другом процессе.
    """

    state_data_cls: Type[StateData] = StateData
    document_filter: dict
    max_tasks: int = 1
    cache_key_suffix: str = ''
    cache_ttl: int | None = None
    projection: dict = {'_id': 1, 'content.id': 1}

    def __init__(self, **kwargs) -> None:
        document_filter: dict = kwargs.get('document_filter', self.document_filter)
        self.cache_key_suffix = kwargs.get('cache_key_suffix', self.cache_key_suffix)

        self.is_active: bool = True
        self.stop_reason: str = ''

        cache_key = self.__class__.__name__
        if self.cache_key_suffix:
            cache_key += ':' + self.cache_key_suffix

        self.state: State[StateData] = State(
            cache_key=cache_key,
            cache_ttl=self.cache_ttl,
            state_data_cls=self.state_data_cls,
        )
        self.state_data: StateData = self.state_data_cls()
        self.document_filter.update(document_filter)

    async def run(self) -> None:
        logger.info('Start running collector')
        await self.load_state_data()

        while self.is_active:
            try:
                tasks = []
                last_id = self.state_data.last_id
                for _ in range(self.max_tasks):
                    activity = await self.get_activity()

                    if activity is None:
                        self.stop('There are no available activities to update')
                        break

                    self.state_data.last_id = activity['_id']
                    tasks.append(self.run_for_activity(activity))

                try:
                    await asyncio.gather(*tasks)
                except Exception:
                    self.state_data.last_id = last_id
                    raise

                self.state_data.activities_count += len(tasks)

            except Exception as err:
                self.stop(f'Unexpected error: {err}')
                raise
            finally:
                await self.save_state_data()

    def stop(self, reason: str) -> None:
        self.is_active = False
        self.stop_reason = reason
        logger.info('Stop collector: %s', reason)

    @property
    def result(self) -> dict:
        return {
            'state_data': jsonable_encoder(self.state_data),
            'stop_reason': self.stop_reason,
        }

    async def load_state_data(self) -> None:
        self.state_data = await self.state.load_data()

    async def save_state_data(self) -> None:
        await self.state.save_data(self.state_data)

    async def get_activity(self) -> 'ActivityDict':
        document_filter = {
            '_id': {'$gt': self.state_data.last_id},
            **self.document_filter,
        }
        count = await ActivityManager().collection.count_documents(document_filter)
        self.state_data.activities_remaining = count
        logger.debug('Getting one activity. Activities remaining to process: %s', count)
        document: ActivityDict | None = await ActivityManager().collection.find_one(
            document_filter,
            self.projection,
            sort=[('_id', 1)],
        )

        return document

    async def run_for_activity(self, activity: 'ActivityDict') -> None:
        raise NotImplementedError


class ActivityContentDict(TypedDict):
    """Activity Content Dict"""

    id: str


class ActivityDict(TypedDict):
    """Activity Dict"""

    _id: ObjectId
    content: ActivityContentDict
