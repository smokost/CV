"""
Отрывок кода


Набор функций для работы с API партнерских программ. Например Admitad API.

Синхронизация статистики и учет оплаты консультантам
"""

import sys

import logging
import traceback

from django.conf import settings
from django.utils import timezone

from admitad import api as admitad_api
from admitad import items as admitad_items
from pprint import pformat

logger = logging.getLogger(__name__)


class AdmitadStatisticsGatherer:
    """
    Класс для сбора и обработки статистики из адмитада.

    Синхронизация статистики адмитада по действиям
    https://developers.admitad.com/ru/doc/api_ru/methods/statistics/statistics-actions/

    Запрашивает список последних действий и сравнивает с уже запомненными в системе.
    Отмечает статус при изменении оригинала.
    Возможные статусы адмитада pending/approved/declined/approved_but_stalled

    Для каждого нового действия, при условии, что это действие связано с витриной
    консультанта (есть параметр subid1 с его user.username), создается MoneyFlow
    с соответствующим статусом. При повторном запросе, если статус у действия
    меняется, то меняется статус экземпляра MoneyFlow.
    """

    moneyflow_mapping = {
        'pending': 'opened',
        'approved': 'approved',
        'declined': 'declined',
        'approved_but_stalled': 'opened',
    }

    ACTIONS_DAYS = 30  # method: _process_actions
    OLD_ACTIONS_DAYS = 1  # method: _process_old_actions

    class CheckActionValueError(ValueError):
        """Ошибка проверки словаря action"""
        pass

    def __init__(self):
        # Для сбора ошибок во время выполнения цикла
        self._exceptions = []
        self._client = None
        self._moneyflow_source = MoneyFlowSource.objects.get(uuid='partner_admitad')

    def run(self):
        """Запуск основного цикла"""
        logger.info('start sync admitad statistics')
        try:
            self._run()
        except Exception:
            logger.exception('AdmitadStatisticsGatherer.run EXCEPTION OCCURRED')
        logger.info('finish sync admitad statistics')

    def _run(self):
        """_Запуск основного цикла"""

        # Получаем клиент Admitad API
        self._get_client()

        # Обрабатываем список действий из адмитада
        self._process_actions()

        # Обрабатываем некоторые неучтенные действия из адмитада
        self._process_old_actions()

        # Если были ошибки при итерации, то выбрасываем ошибку по первой из них
        if self._exceptions:
            len_errors = len(self._exceptions)
            logger.warning('gathered %s exceptions', len_errors)
            raise self._exceptions[0]

    def _get_client(self):
        """Получение клиента API"""

        client_id = settings.ADMITAD_CLIENT_ID
        client_secret = settings.ADMITAD_CLIENT_SECRET
        scope = ' '.join({
            admitad_items.Me.SCOPE,
            admitad_items.StatisticActions.SCOPE,
            admitad_items.StatisticSubIds.SCOPE,
        })

        self._client = admitad_api.get_oauth_client_client(
            client_id,
            client_secret,
            scope
        )

        logger.info('client init successful')

    def _process_actions(self):
        """Обработка списка действий из адмитада"""

        logger.info('start _process_actions')

        # Получаем список действий
        actions = self._get_admitad_actions()

        # Итерируем по всем действиям
        for action in actions:
            try:
                self._process_action(action)
            except self.CheckActionValueError as err:
                logger.warning(str(err))
            except Exception as err:
                self._handle_exception('PROCESS ACTION ERROR OCCURRED', err)

        logger.info('finish _process_actions')

    def _process_old_actions(self):
        """
        Обработка неучтенных действий

        Денежные средства по некоторым действиям могут быть
        "в обработке (pending)" немного дольше того периода,
        за который получен список actions в _get_admitad_actions, поэтому
        необработанные денежные потоки адмитада нужно проработать отдельно
        """

        logger.debug('start _process_old_actions')

        # Находим действия, которые не были обновлены за предыдущий цикл
        utime__lte = timezone.now() - timezone.timedelta(days=self.OLD_ACTIONS_DAYS)
        admitad_moneyflow_instances = AdmitadMoneyFlow.objects.filter(
            status__in=['pending', 'approved_but_stalled'],
            utime__lte=utime__lte,
        )

        # Подсчет количества
        _count = admitad_moneyflow_instances.count()
        if _count > 0:
            logger.debug('found %s old actions', _count)

            # Итерация. Нам нужны только action_id
            for admitad_moneyflow_instance in admitad_moneyflow_instances.values('action_id'):
                action_id = admitad_moneyflow_instance['action_id']
                logger.debug('process %s', action_id)
                try:
                    # Загружаем через API объект
                    action = self._get_admitad_action(action_id)
                    if action is not None:
                        self._process_action(action)
                    else:
                        logging.debug('action %s was not found in Admitad', action_id)
                except self.CheckActionValueError as err:
                    logger.warning(str(err))
                except Exception as err:
                    self._handle_exception('PROCESS OLD ACTION ERROR OCCURRED', err)
        else:
            logger.debug('there is no old actions')
        logger.debug('finish _process_old_actions')

    def _get_admitad_actions(self):
        """Получение списка действий из Адмитада"""

        # Получаем список действий за последние ACTIONS_DAYS дней у адмитада
        date = timezone.now() - timezone.timedelta(days=self.ACTIONS_DAYS)
        date = date.strftime('%d.%m.%Y')
        actions_result = self._client.StatisticActions.get(date_start=date, subid4='sarafanka')
        logger.debug(
            'gathered %s actions:\n%s',
            actions_result['_meta']['count'],
            pformat(actions_result, indent=2, width=120),
        )
        return actions_result['results']

    def _get_admitad_action(self, action_id):
        """Получение детальной по действию из Адмитада"""

        actions_result = self._client.StatisticActions.get(action_id=action_id, subid4='sarafanka')
        logger.debug(
            'gathered %s actions:\n%s',
            actions_result['_meta']['count'],
            pformat(actions_result, indent=2, width=120),
        )
        return actions_result['results'][0] if actions_result['results'] else None

    def _handle_exception(self, message, err, silent=True):
        """Обработка ошибки"""

        if silent:
            logger.warning('%s:\n%s', message, str(err))
            traceback.print_exc(file=sys.stdout)
        else:
            logging.exception('%s:\n%s', message, str(err))
        self._exceptions.append(err)

    def _process_action(self, action: dict):
        """
        Обработка конкретного действия.

        Создаем новый MoneyFlow или редактируем старый.
        """

        # Проверка словаря action
        self._check_action_dict(action)

        # Создаем новый или получаем старый денежный поток из адмитада
        admitad_moneyflow_instance = self._get_admitad_moneyflow_instance(action)

        # Пропускаем, если экземпляр существует в БД и статус среди ['approved', 'declined']
        if admitad_moneyflow_instance.status in ['approved', 'declined']:
            logger.debug('admitad_moneyflow_instance.status is %s, skip', admitad_moneyflow_instance.status)
            return

        # Обновляем статус
        self._update_moneyflow_status(admitad_moneyflow_instance, action['status'])

    def _get_admitad_moneyflow_instance(self, action: dict):
        """Получение экземпляра AdmitadMoneyFlow для действия"""

        action_id = action['action_id']

        # Поиск в БД через action_id
        admitad_moneyflow_instance = AdmitadMoneyFlow.objects.filter(
            action_id=action['action_id']
        ).first()

        debug_message = 'an old admitad_moneyflow found: %s'
        if admitad_moneyflow_instance is None:
            # Если в БД не найдено, то создаем новое

            # user.username хранится в параметре subid1, согласно
            # showcaseapp.deeplink_backends.DeepLinkBackendProcessor_admitad_backend
            member_instance = Member.objects.get(user__username=action['subid1'])

            moneyflow_instance = self._moneyflow_source.create_moneyflow(
                user=member_instance.user,
                flowtype='push',
                value=float(action['payment']),
                comment=f'admitad action {action_id}'

            )
            admitad_moneyflow_instance = AdmitadMoneyFlow.objects.create(
                action_id=action_id,
                moneyflow=moneyflow_instance
            )
            debug_message = 'a new admitad_moneyflow created: %s'

        logger.debug(
            debug_message,
            str(admitad_moneyflow_instance)
        )

        return admitad_moneyflow_instance

    def _update_moneyflow_status(self, instance: AdmitadMoneyFlow, status):
        """
        Обновление статуса денежного потока

        Если статус не изменился, то save не произойдет
        """

        debug_text = 'status of MoneyFlow %s not updated'
        if instance.status != status:
            debug_text = 'status of MoneyFlow %s updated to ' + status
            instance.status = status
            instance.moneyflow.status = self.moneyflow_mapping[status]
            instance.save(update_fields=['status', 'utime'])
            instance.moneyflow.save(update_fields=['status', 'utime'])

        logger.debug(debug_text, str(instance))

    def _check_action_dict(self, action: dict):
        """Проверка словаря action"""

        # Проверка необходимых полей
        check_action_fields = [
            'subid1',
            'subid4',
            'action_id',
            'payment',
            'status',
        ]
        check_action_list = list(map(
            lambda x: action.get(x) is not None,
            check_action_fields
        ))
        check = all(check_action_list)
        if not check:
            raise self.CheckActionValueError(
                f'check_action fields fail:'
                f'{list(zip(check_action_fields, check_action_list))}'
            )

        # Проверка статусов
        _check = action['status'] in self.moneyflow_mapping
        if not _check:
            logger.debug(
                'check_action fail: %s\n%s',
                list(zip(check_action_fields, check_action_list)),
                action
            )
            raise self.CheckActionValueError(
                f'check_action status fail: {action["status"]}'
            )


def sync_admitad_statistics():
    """
    Запуск синхронизации
    """
    try:
        gatherer = AdmitadStatisticsGatherer()
    except Exception:
        logging.exception('init sync_admitad_statistics ERROR OCCURRED')
    else:
        gatherer.run()
        return gatherer
