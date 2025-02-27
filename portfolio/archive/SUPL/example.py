'''
Образец кода CSV экспортера
'''

class AbstractCSVExporter(ABC):
    """
    Абстрактный класс для экспорта данных в CSV файл
    """

    # Время хранения ключа в кэше
    cache_expire_seconds = 60 * 10

    # Номер БД Redis для подключения
    _redis_db = RedisDBEnum.BACK_OFFICE

    # Имя логгера
    logger_name = __name__

    # Ключи для Redis
    redis_progress_key: str
    redis_file_name_key: str
    # Номер итерации, на котором происходит обновление
    # ключа redis_progress_key
    _progress_key_step = 100

    # Ключи для Storage
    storage_file_name_prefix: str

    # Класс для получения полей строки CSV таблицы
    rows_iterator_class: AbstractCSVRowsIterator

    def __init__(self) -> None:

        # Проверка аннотаций на предмет реализации в дочернем классе
        for attr in self.__annotations__:
            if not hasattr(self, attr):
                error = f'Attribute \'{attr}\' should be implemented'
                raise NotImplementedError(error)

        # Инстанс подключения к Redis
        self.redis = FileExportRedisHelper(
            self._redis_db,
            self.redis_progress_key,
            self.redis_file_name_key,
            self.cache_expire_seconds,
        )

        self.logger = logging.getLogger(self.logger_name)

    def get_keys_as_dict(self):
        """Возвращает все ключи"""
        return {
            'progress': self.redis.get_progress(),
            'file_url': self.redis.get_file_name(),
        }

    def is_in_progress(self):
        """Проверка статуса выполняемой задачи на экспорт"""
        progress = self.redis.get_progress()

        if not progress or int(progress) == 100:
            return False

        return True

    def _write_rows(self, writer, rows):
        """Записывает строки в CSV файл"""

        total = len(rows)

        # Запись заголовка
        writer.writerow(rows.get_header_row())

        for i, row in enumerate(rows, start=1):
            # Запись строки
            writer.writerow(row)

            if i % self._progress_key_step == 0:
                # Обновление статуса о прогрессе
                progress = int((i / total) * 100)
                self.redis.set_progress_key(progress)

        self.redis.set_progress_key(100)

    def get_storage_file_name(self, file):
        """Генерирует имя файла для хранилища"""

        now = timezone.now()
        return (
            f'{self.storage_file_name_prefix}'
            f'{now.year}/{now.month}/{now.day}'
            f'{file.name}.csv'
        )

    def _upload_file_to_storage(self, file):
        """Загрузка файла в хранилище.
        Записывает ссылку на файл в Redis для последующей загрузки
        """

        # Если не переоткрывать файл в режиме "rb", то может возникнуть ошибка
        # TypeError: memoryview: a bytes-like object is required, not 'str'
        _file = open(file.name, 'rb')
        try:
            file_url = upload_file_to_storage(
                self.get_storage_file_name(file),
                _file,
            )
        except Exception as e:  # pylint: disable=broad-except
            # pylint: disable=logging-too-many-args
            self.logger.exception(
                '%s ERROR',
                self.__class__.__name__,
                extra={'exception': e},
            )
        else:
            # Обновление ключа со ссылкой на файл в Redis
            self.redis.set_file_name_key(file_url)
        finally:
            _file.close()

    def export_to_csv(self, *args, **kwargs):
        """Выгружает в csv файл"""

        # Выход, если процесс уже запущен
        if self.is_in_progress():
            return

        # Создаем временный файл для записи CSV таблицы
        file = tempfile.NamedTemporaryFile('w+')

        try:
            # Получение генератора со строками CSV
            rows = self.rows_iterator_class(*args, **kwargs)

            # Запись строк в файл
            with open(file.name, 'w+') as f:
                writer = csv.writer(f)
                self._write_rows(writer, rows)

            # Загрузка файла в хранилище
            self._upload_file_to_storage(file)
        finally:
            # Временный файл будет удален после закрытия
            file.close()
