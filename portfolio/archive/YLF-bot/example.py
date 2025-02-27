"""
Отрывок кода
"""


# Модуль содержит объекты-классы, в которых описаны необходимые данные для регистрации или конкретного функционала
from src.BaseClass import (
    BaseCallData,
    BaseButtonClass,
    MenuItemMixin,
)
from src.Menus import (
    MainMenu,
    RegisterContinueMenu,
    QRMenu,
    RegisterMenu,
    # menu_dict,
    BaseMenu,
    PaymentMenu,
    MeetupSecretaryMenu,
)
from src.QRCode import get_addition_custom_classes
from utils.bot_user_utils import (
    update_msg_to_user,
    update_keyboard_to_user,
)
from utils.exceptions import APIResponseError
from utils.mongodb_utils import db
from utils.regex_utils import validate_phone
from utils.variables import (
    profile_registration_checks,
    allowed_snt_list,
)
from utils.yafunc_api import (
    make_post_request,
    get_bill_qr,
    download_registered_documents,
    check_validation_code,
    check_user_profile_in_db,
    send_validation_sms,
    get_delegate_question,
    get_delegate_bulletin,
    answer_delegate_bulletin,
    confirm_delegate_bulletin,
    get_street_name,
    get_snt_name,
    get_kadastr_num,
    find_user_profile,
    get_street_id,
)


class RegisterProfileBase(MenuItemMixin, BaseCallData):
    """Регистрация базового профиля"""
    call_data_key = 'registerProfileBase'
    call_data_translate = 'Ввести данные профиля'
    questions = [
        # '108',
        '101', '100', '102', '113', '110', '111', '112',
        # '103',
        '103.2', '104', '115', '116', '109', '105', '106', '107'
    ]
    fields = {
        'name': 'Имя',
        'lastname': 'Фамилия',
        'grandname': 'Отчество',
        'strID': 'Улица',
        'numsite': '№ дома / участка',
        'checkKadastrNum': None,
        'kadastrNum': 'Номер кадастра',
        'snt': 'СНТ',
        'phone': 'Телефон',
        'isFZ152Agreed': 'Согласие на обработку',
        'isRegisteredAtSNT': 'Прописка по адресу СНТ',
        'saveUserData': 'Согласие на сохранение',
        'isValidated': None,
        'through': None,
        'mAppKey': None,
        'isDelegate': 'Делегат?',
        'isOwnerAtSNT': 'Собственник?',
        'membership': 'Член СНТ?',
        'gender': 'Пол',
    }
    call_data_kwargs = {'delete': False}

    def get_call_data_function(self, test=False, delete=True):
        """Создание нового пользователя в БД.
        Запускает регистрацию базового профиля
        """
        print("Процесс регистрации базового профиля")
        if test:
            # Для тестов
            self.user.update({'step': 8,
                              'name': 'имя', 'lastname': 'фамилия', 'grandname': 'отчество', 'phone': '79865421358',
                              'strID': '1210', 'numsite': '78', 'saveUserData': True, 'isFZ152Agreed': True,
                              'counterType': '1'})
            self.msg.data = 'Да'
        else:
            self.user.update({self.call_data_key: None})
        self.user.update({'isValidated': True})
        if delete:
            db.bot_users.delete_one({'telegramID': self.msg.from_user.id})
            db.bot_users.insert_one(self.user)

    def call_data_function(self, *args, **kwargs):
        super(RegisterProfileBase, self).call_data_function(check_user_profile=False, *args, **kwargs)

    def get_question(self, qi, request=None):
        """Дополнительный параметр в запрос, если запрашивается улица"""
        request = request or {}

        if qi == '103.2':
            request.update({
                'snt': self.user['snt']
            })

        return super(RegisterProfileBase, self).get_question(qi, request=request)

    def register_continue(self):
        """Подправленное продолжение регистрации"""
        super(RegisterProfileBase, self).register_continue()
        for field in profile_registration_checks:
            self.user[field] = None
        self.user['checked'] = True
        self.msg.text = self.user['phone']

    def check_pre_question(self):
        """Проверка отрицательного ответа на вопрос о сохранении данных и согласии"""
        if not self.user.get('registerProfileBase') and (
                self.user.get('saveUserData') is False or self.user.get('isFZ152Agreed') is False):
            update_msg_to_user(self.user, {'text': 'Вы не согласились сохранять данные, регистрация окончена'})
            self.user['need_to_delete'] = True
            return True

    def check_answer_addition_text(self, question, data):
        """Дополнительные действия для текста в функции check_answer_another"""
        # Проверка телефона
        if question['name'] == 'phone':
            # Проводить проверку в БД по номеру телефона
            p = validate_phone(data)
            if p is None:
                update_msg_to_user(self.user, {'text': 'Введите номер телефона в формате 7XXXXXXXXXX'})
                return data, True
            self.set_profile_field(question['name'], p)
            if check_user_profile_in_db(self.user):  # Поиск профиля пользователя в БД
                return data, RegisterContinueMenu(self.user).send_menu()
        return super(RegisterProfileBase, self).check_answer_addition_text(question, data)

    def check_answer_addition_buttons(self, question, data):
        data, addition = super(RegisterProfileBase, self).check_answer_addition_buttons(question, data)

        if question['name'] == 'checkKadastrNum':
            if data is True:
                self.set_profile_field('kadastrNum', self.user['kadastrNum'])

        return data, addition

    def get_conditions(self, question):
        condition = super(RegisterProfileBase, self).get_conditions(question)

        # Запрос параметров кадастра для вопроса 115
        if question['name'] == 'checkKadastrNum':
            try:
                kadastr = get_kadastr_num(self.user)
            except APIResponseError as err:
                # Если запрос неудачный, то переходим к следующему вопросу 116
                if err.response['Error'] == 'Threre is no such kadastr':
                    self.user['checkKadastrNum'] = False
                    condition = False
                else:
                    raise err
            else:
                # Если запрос удачный, то присваеваем найденный номер кадастра и задаем вопрос 115
                self.user['kadastrNum'] = kadastr['kadastrNum']

        return condition

    def update_question_text_and_buttons(self, question, question_text, buttons):
        if question['name'] == 'checkKadastrNum':
            # Дополняем вопрос запрошенным ранее номером кадастра
            question_text += f'\n{self.user["kadastrNum"]}'
        return super(RegisterProfileBase, self).update_question_text_and_buttons(question, question_text, buttons)

    def api_function(self, request):
        """Отправка запроса для регистрации базового профиля"""
        response = make_post_request('registerProfileBase', request).get('response', {})
        self.user['profileID'] = response['profileID']

    def get_translated_value(self, field):
        """Дополнительные действия при переводе введенных в опросе полей"""
        if field == 'strID':
            return get_street_name(self.user)
        elif field == 'gender':
            return 'М' if self.user[field] == 'male' else 'Ж'
        elif field == 'snt':
            return get_snt_name(self.user[field])
        return super(RegisterProfileBase, self).get_translated_value(field)


class RegisterProfileElectricityCount(MenuItemMixin, BaseCallData):
    """Регистрация профиля для приема электричества"""
    call_data_key = 'registerProfileElectricityCount'
    call_data_translate = 'Ввести данные для учета электричества'
    questions = [
        '200', '252', '253', '254', '255', '257', '258'
    ]
    fields = {
        'profileID': None,
        'counterType': 'Тип счетчика',
        'counterModel': 'Модель счетчика',
        'counterSN': 'Серийный номер счетчика',
        'counterSetupDate': 'Дата установки счетчика',
        'uzoAmpers': 'Номинал вводного автомата',
        'transformator': 'transformator',
        'feeder': 'feeder',
        'sealNum': 'Номер пломбы',
        'sealPhoto': 'Фото пломбы',
    }

    def get_call_data_function(self, *args, **kwargs):
        """Начало регистрации параметров счечтика"""
        print('Начало регистрации параметров счетчика')
        self.user.update({'transformator': '', 'feeder': ''})

    def api_function(self, request):
        """Отправка запроса для регистрации данных о счетчике"""
        download_registered_documents(self.user, request, 'sealPhoto')
        return make_post_request('registerProfileElectricityCount', request).get('response', {})


class RegisterProfileElectricityPayment(MenuItemMixin, BaseCallData):
    """Регистрация профиля для приема оплаты электричества"""
    call_data_key = 'registerProfileElectricityPayment'
    call_data_translate = 'Внести показания первый раз'
    questions = [
        '200', '210', '211', '220', '221', '222', '223'
    ]
    fields = {
        'profileID': None,
        'counterType': 'Тип счетчика',
        't1Paid': 'T1 предыдущий',
        't1Current': 'Т1 текущий',
        't2Paid': 'Т2 предыдущий',
        't2Current': 'Т2 текущий',
    }

    def get_call_data_function(self, *args, **kwargs):
        """Инициализирует регистрацию показаний счетчика при нажатии на кнопку"""
        print('Начало внесения показаний счетчика')
        self.user.update({'t2Paid': '', 't2Current': ''})
        self.user.pop('counterType', None)

    def register_continue(self):
        """Продолжение регистрации"""
        super(RegisterProfileElectricityPayment, self).register_continue()
        self.user.pop('electricity', None)

    def function_to_process(self):
        """Функция, которая сработает в конце регистрации"""
        self.user['state'] = 'getElectricityBillQr'
        return QRMenu(self.user).send_menu(qr_type='electricity', check_type=False)

    def api_function(self, request):
        """Отправка запроса для внесения показаний счетчика"""
        # user['electricity'] = {}
        response = make_post_request('registerProfileElectricityPayment', request).get('response', {})
        update_msg_to_user(self.user, {'text': 'Данные внесены успешно'})
        return response


class SaveCounterData(MenuItemMixin, BaseCallData):
    """Регистрация показаний счетчика"""
    call_data_key = 'saveCounterData'
    call_data_translate = 'Внести новые показания'
    questions = [
        '200', '211', '222', '223'
    ]
    fields = {
        'profileID': None,
        't1Current': 'Т1 текущий',
        't2Current': 'Т2 текущий',
    }

    def get_call_data_function(self, *args, **kwargs):
        """Инициализация регистрации следуюших показаний счетчика"""
        if 'electricity' in self.user and ('losses' not in self.user or self.user['losses']['status'] != 'accepted'):
            text = '⭕️Чтобы внести новые показания счетчика, сначала нужно оплатить 15% потерь за предыдущий чек.'
            # update_msg_to_user(user, {'text': text, 'parse_mode': 'HTML'})
            return MainMenu(self.user).send_menu(text, check_profile=False)

        print('Начало внесения новых показаний счетчика')
        self.user.update({'t2Current': ''})
        if self.user.get('electricity') is not None and self.user['electricity'].get('status') != 'accepted':
            return RegisterContinueMenu(self.user).send_menu()
        self.user.pop('electricity', None)

    def register_continue(self):
        """Продолжение регистрации"""
        super(SaveCounterData, self).register_continue()
        self.user.pop('electricity', None)

    def function_to_process(self):
        """Функция, которая сработает в конце регистрации"""
        self.user['state'] = 'getElectricityBillQr'
        return QRMenu(self.user).send_menu(qr_type='electricity', check_type=False)

    def api_function(self, request):
        """Отправка запроса для повторного внесения показаний счетчика"""
        response = make_post_request('saveCounterData', request, raise_error=False)
        # user['electricity'] = {}
        if 'Error' in response:
            if 'At least one counterData document from that user is required' in response['Error']:
                if 'registerProfileElectricityPayment' in self.user:
                    del self.user['registerProfileElectricityPayment']
                if 'electricity' in self.user:
                    del self.user['electricity']
                mes = '❗ Вы не вводили или не оплатили начальные показания ❗'
                MainMenu(self.user).send_menu(mes)
                # Выводить ошибку и предлагать ввести данные для счетчика заново
            elif 'Incoming data less than previous' in response['Error']:

                mes = '❗ Значения введенных показаний ниже, чем предыдущие ❗\n'
                mes += 'Т1 предыдущий: ' + str(response.get('response', {})['t1Paid']) + '\n'
                mes += 'Т1 текущий: ' + str(response.get('response', {})['t1Current']) + '\n'
                if self.user['counterType'] in [2, '2']:
                    mes += 'Т2 предыдущий: ' + str(response.get('response', {})['t2Paid']) + '\n'
                    mes += 'Т2 текущий: ' + str(response.get('response', {})['t2Current']) + '\n'
                mes += '\n Выберите действия'
                MainMenu(self.user).send_menu(mes)
                get_bill_qr(self.user, {'profileID': self.user['profileID']},
                            'electricity')  # формирует поле user[qr_type]
            else:
                raise ValueError(response)
        else:
            update_msg_to_user(self.user, {'text': 'Данные внесены успешно'})
        return response.get('response', {})


class RegisterProfileMUKPayment(MenuItemMixin, BaseCallData):
    """Регистрация профиля для оплаты МУК"""
    call_data_key = 'registerProfileMukPayment'
    call_data_translate = 'Ввести данные для оплаты за мусор'
    questions = [
        '300', '301', '302'
    ]
    fields = {
        'profileID': None,
        'humanCount': 'humanCount',
        'mukAccountId': 'mukAccountId',
        'mukPassword': 'mukPassword',
    }

    def get_call_data_function(self, *args, **kwargs):
        """Инициализация регистрации профиля для оплаты мусора"""
        print('Начало регистрации параметров для оплаты мусора')
        self.user.update({'paymPeriod': None})

    def api_function(self, request):
        """Отправка запроса для внесения профиля для оплаты мусора"""
        return make_post_request('registerProfileMukPayment', request).get('response', {})


class RegisterProfileMembership(MenuItemMixin, BaseCallData):
    """Регистрация профиля членства"""
    call_data_key = 'registerProfileMembership'
    call_data_translate = 'Ввести данные для оплаты членских взносов'
    questions = [
        '400'
    ]
    fields = {
        'profileID': None,
        'kadastrNum': 'kadastrNum',
    }

    def get_call_data_function(self, *args, **kwargs):
        """Инициализация регистрации профиля для оплаты членского взноса"""
        print('Начало регистрации параметров для оплаты членского взноса')

    def api_function(self, request):
        """Отправка запроса для внесения профиля для членского взноса"""
        try:
            response = make_post_request('registerProfileMembership', request).get('response', {})
        except Exception as err:
            if '404 not found' in str(err).lower():
                update_msg_to_user(self.user, {
                    'text': 'Не удалось закончить регистрацию. Похоже, номер кадастра неверен.'
                })
                self.user['registerProfileMembership'] = False
                return
            else:
                raise err
        return response


class RegisterProfileVotingDocument(MenuItemMixin, BaseCallData):
    """Регистрация какого-то непонятного документа"""
    call_data_key = 'registerProfileVotingDocument'
    call_data_translate = 'Ввести данные для голосования на общем собрании'
    questions = [
        '400', '401', '410', '411', '412', '413', '414'
    ]
    fields = {
        'profileID': None,
        'kadastrNum': 'kadastrNum',
        'email': 'email',
        'membership': 'Член СНТ?',
        'documentNum': 'documentNum',
        'admissionDate': 'admissionDate',
        'membershipRequest': 'membershipRequest',
        'docPhoto': 'docPhoto',
    }

    def get_call_data_function(self, *args, **kwargs):
        """Инициализация регистрации профиля документа голосования"""
        print('Начало регистрации параметров для профиля документа голосования')
        self.user.update({'documentNum': None, 'admissionDate': None, 'membershipRequest': None})

    def api_function(self, request):
        """Отправка запроса для внесения профиля документа голосования"""
        download_registered_documents(self.user, request, 'docPhoto')
        return make_post_request('registerProfileVotingDocument', request).get('response', {})


class RegisterProblem(MenuItemMixin, BaseCallData):
    """Регистрация проблемы"""
    call_data_key = 'registerProblem'
    call_data_translate = 'Сообщить о проблеме'

    questions = [
        '601', '602', '603', '604', '605', '606'
    ]  # '607' - Убрал за ненадобностью
    fields = {
        'profileID': None,
        'photoProblem': 'Фото проблемы',
        'tags': 'Отмеченные теги проблемы',
        'geoPoint': 'Координаты',
        'commentProblem': 'Комментарий',
        'audioProblem': 'Аудио комментарий',
        'videoProblem': 'Видео комментарий',
        # 'saveProblemData': 'Сохранить данные?', - Убрал за ненадобностью
    }

    def get_call_data_function(self, *args, **kwargs):
        """Инициализация регистрации проблемы"""
        print('Начало регистрации проблемы')
        RegisterContinueMenu(self.user).send_menu()

    def check_answer_addition_buttons(self, question, data):
        """Дополнительные действия для кнопок в функции check_answer_another"""
        if question['type'] == 'tags':
            for i, btn in enumerate(self.user[question['name']], 1):
                if btn['value'] == data:
                    btn[f'tag{i}'] = not btn[f'tag{i}']
                    break
            else:
                def check():
                    update_msg_to_user(self.user, {'text': f'Этот тег не поддерживается: {data}'})
                    return data, True

                return (data, False) if self.user.pop('questions_tag_done', None) else check()
            self.user['step'] -= 1
            if question['name'] not in self.user['fields_entered']:
                self.user['fields_entered'] += [question['name']]
            return data, False
        return super(RegisterProblem, self).check_answer_addition_buttons(question, data)

    def api_function(self, request):
        """Отправка запроса на регистрацию проблемы"""
        download_registered_documents(self.user, request, ['photoProblem', 'audioProblem', 'videoProblem'])
        request['through'] = 'tlgrbot'
        return make_post_request('registerProblem', request).get('response', {})

    def get_translated_value(self, field):
        """Дополнительные действия при переводе введенных в опросе полей"""
        if field == 'geoPoint':
            return str(self.user[field])
        elif field == 'tags':
            return ', '.join([t['value'] for i, t in enumerate(self.user['tags'], 1) if t[f'tag{i}']])
        return super(RegisterProblem, self).get_translated_value(field)


class ChoosingMyDelegate(BaseCallData):
    """Выборы делегата"""
    call_data_key = 'choosingMyDelegate'
    call_data_translate = 'Выбрать делегата'
    questions = [
        '500', '500.1', '500.2', '501.1',
        # '501',
        # '502', '503'
    ]
    fields = {
        'profileID': None,
        'mAppKey': None,
        'myDelegateID': 'ID выбранного делегата',
        'bulletin': None,
        'bulletinID': None,
        'votingKey': 'Проверочный код',
        'voterID': None,
        'voterRight': None,
        'answer': 'Ответ',
    }

    def get_call_data_function(self, *args, **kwargs):
        """Инициализация выбора и голосования за делегата"""
        print('Начало выборов делегата')
        self.user.pop('votingKey', None)
        self.user.pop('bulletinID', None)

    def get_row_width(self, question):
        """Количество кнопок в строке для myDelegateID"""
        if question['name'] == 'myDelegateID':
            return 1
        return super(ChoosingMyDelegate, self).get_row_width(question)

    def get_page_len(self, question):
        """Количество кнопок на странице для myDelegateID"""
        if question['name'] == 'myDelegateID':
            return 5
        return super(ChoosingMyDelegate, self).get_page_len(question)

    def update_question_text_and_buttons(self, question, question_text, buttons):
        """Дополнительные действия перед каждым вопросом"""
        args = [question, question_text, buttons]
        question_text, buttons = super(ChoosingMyDelegate, self).update_question_text_and_buttons(*args)
        # Информация о делегате
        if question['name'] == 'bulletinID':
            response = get_delegate_question(self.user)
            answers = '", "'.join(response["Условия Голосования"]["Варианты Ответа"])
            question_text += (
                '\n\n'
                f'Идентификационный номер кандидата: {response["Идентификационный номер кандидата"]}\n'
                f'ФИО: {response["Кандидат"]}\n'
                f'Вопрос: {response["Условия Голосования"]["Вопрос"]}\n'
                f'Варианты ответа: "{answers}"\n\n'
                f'Проголосовать за данного делегата?'
            )

        # Подставляем вопрос и варианты ответа из бюллетеня
        elif question['name'] == 'answer':
            question = self.user['bulletin']['conditions']['Вопрос']
            # link = user['bulletin']['links']['Ссылка на печать']
            question_text += (
                    '\n\n' +
                    f'{question}'
                # f'\n\nСсылка на печать бюллетеня: {link}'
            )

            answered = self.user['bulletin']['answered']
            if answered:
                question_text += f'\n\nОтвет уже был дан по этому бюллетеню ранее: "{answered}"!'
                buttons += [('Продолжить', answered)]
            else:
                for answer in self.user['bulletin']['conditions']['Варианты Ответа']:
                    buttons += [(answer, answer)]

        elif question['name'] == 'votingKey':
            question_text += ' ' + str(self.user['phone'])
        elif question['name'] == 'myDelegateID':
            question_text += '\n\nДля возврата в главное меню введите /main_menu'
        return question_text, buttons

    def get_question(self, qi, request=None):
        """Дополнительный параметр в запрос"""
        request = request or {}

        if qi == '500':
            request.update({
                'snt': self.user['snt']
            })

        return super(ChoosingMyDelegate, self).get_question(qi, request=request)

    def check_answer_addition_buttons(self, question, data):
        """Дополнительные проверки нажатых кнопок для выполнения запросов"""
        args = [question, data]
        data, addition = super(ChoosingMyDelegate, self).check_answer_addition_buttons(*args)
        # Запрос на получение бюллетеня
        if data == 'getDelegateBulletin':
            response = get_delegate_bulletin(self.user)
            self.user['bulletin'] = response
            data = response['bulletinID']
            self.user['voterID'] = response['voterID']
            self.user['voterRight'] = response['voterRight']

        # Запрос на ответ по бюллетеню
        if question['name'] == 'answer' and not self.user['bulletin']['answered']:
            self.set_profile_field(question['name'], data)
            answer_delegate_bulletin(self.user)

        return data, addition

    def check_answer_addition_text(self, question, data):
        """Дополнительные действия для текста в функции check_answer_another"""
        args = [question, data]
        data, addition = super(ChoosingMyDelegate, self).check_answer_addition_text(*args)

        # Проверка введенного votingKey на этапе выбора делегата
        if question['name'] == 'votingKey':
            self.set_profile_field(question['name'], data)
            confirm_delegate_bulletin(self.user)

        return data, addition

    def api_function(self, request):
        """Отправка запроса для внесения данных о голосовании за делегата в профиль"""
        return {}


class RegisterContinue(MenuItemMixin, BaseCallData):
    """Продолжение регистрации"""
    call_data_key = 'register_continue'
    call_data_translate = 'Продолжить'

    class Button(BaseButtonClass):
        order = 0
        menu_class = RegisterContinueMenu

    button_classes = [
        Button
    ]

    def call_data_function(self, *args, **kwargs):
        """Продолжение регистрации после вопроса"""
        self.user['state'] = self.user['state'].replace('_asking', '')
        if self.user['state'] in call_data_dict:
            obj = call_data_dict.get(self.user['state'])(self.user, self.msg)
            return obj.register_continue()


class QuestionDocumentDone(BaseCallData):
    """Обработка документа по вопросу завершена"""
    call_data_key = 'questions_document_done'

    def call_data_function(self, *args, **kwargs):
        self.user.update(questions_document_done=True)


class QuestionTagDone(BaseCallData):
    """Обработка тегов по вопросу завершена"""
    call_data_key = 'questions_tag_done'

    def call_data_function(self, *args, **kwargs):
        self.user.update(questions_tag_done=True)


class GetDetails(MenuItemMixin, BaseCallData):
    """Получение детальной информации о СНТ"""
    call_data_key = 'getDetails'
    call_data_translate = 'Получить реквизиты'

    class Button(BaseButtonClass):
        """Кнопка в главное меню"""
        order = 6
        menu_class = MainMenu

        def check_permission(self):
            return (
                    self.user.get('authorization') and
                    self.user.get('snt', 'sntzhd') in allowed_snt_list and
                    self.user.get('registerProfileBase') is True
            )

    button_classes = [
        Button
    ]

    def call_data_function(self, *args, **kwargs):
        """Получение реквизитов пользователя"""
        text = 'Наименование: СНТ "ЖЕЛЕЗНОДОРОЖНИК"\n' \
               'Расчетный счет: 40703810007550006617\n' \
               'Банк: Филиал «Центральный» Банка ВТБ (ПАО) в г. Москве\n' \
               'БИК: "044525411",\n' \
               'К/c: "30101810145250000411"\n' \
               'КПП: "231201001"\n' \
               'ИНН: "2312088371"\n' \
               'Тариф для однотарифного счетчика: 5.02\n' \
               'Ночной тариф для двутарифного счетчика: 3.02\n' \
               'Дневной тариф для двутарифного счетчика: 5.62'
        update_msg_to_user(self.user, {'text': text})
        return MainMenu(self.user).send_menu()


class ProcessFunction(BaseCallData):
    """Обработка функции после окончания регистрации"""
    call_data_key = 'processFunction'
    call_data_translate = 'Сохранить введенные данные'

    def call_data_function(self, *args, **kwargs):
        """Обработка функции после окончания регистрации профиля"""
        # state = user['state'].split('_')[0]
        state = self.user['state'].replace('_confirmation', '')
        self.user['functions_to_process'] = self.user.get('functions_to_process', []) + [state]
        self.user[state] = True

        if state in call_data_dict:
            obj = call_data_dict.get(state)(self.user, self.msg)
            return obj.function_to_process()
        return MainMenu(self.user).send_menu()


class GetElectricityMap(MenuItemMixin, BaseCallData):
    """Получение карты оплаты по электричеству"""
    call_data_key = 'getElectricityMap'
    call_data_translate = 'Получить статистику оплат'

    class Button(BaseButtonClass):
        """Кнопка в главное меню"""
        order = 4
        menu_class = MainMenu

        def check_permission(self):
            return (
                    self.user.get('authorization') and
                    self.user.get('snt', 'sntzhd') in allowed_snt_list and
                    self.user.get('registerProfileBase') is True and
                    self.user.get('registerProfileElectricityPayment')
            )

    button_classes = [
        Button
    ]

    def call_data_function(self, *args, **kwargs):
        """Получение списка оплат по улицам и формирование общей статистики"""
        response = make_post_request(self.call_data_key, {"snt": "sntzhd"})['response']
        str_dict = {}
        for i in response:
            if not i.get('strID') or i.get('status', '').lower() != 'accepted':
                continue
            str_dict[i['strID']] = str_dict.get(i['strID'], 0) + i.get('t1Sum', 0) + i.get('t2Sum', 0)
        if str_dict:
            text = f'{"Улица":>10} | {"Сумма":<10}\n'
            for str_id, sum_ in str_dict.items():
                text += f'{str_id:>10} | {sum_:<10.2f}\n'
            text = '```' + text + '```'
        else:
            text = 'Пока нет статистики'
        update_msg_to_user(self.user, {'text': text, 'parse_mode': 'MarkdownV2'})
        return MainMenu(self.user).send_menu()


class RegisterMenuCall(MenuItemMixin, BaseCallData):
    """Отправка меню с регистрацией"""
    call_data_key = 'register_menu'
    call_data_translate = 'Регистрация'

    class Button(BaseButtonClass):
        """Кнопка в главное меню"""
        order = 0
        menu_class = MainMenu

        def check_permission(self):
            return (
                    any(map(lambda x: not self.user.get(x), profile_registration_checks)) and
                    self.user.get('authorization')
            )

    button_classes = [
        Button
    ]

    def call_data_function(self, *args, **kwargs):
        """Отправка меню с регистацией"""
        RegisterMenu(self.user).send_menu()


class MainMenuCall(MenuItemMixin, BaseCallData):
    """Отправка главного меню"""
    call_data_key = 'main_menu'
    call_data_translate = 'Главное меню'

    class Button(BaseButtonClass):
        order = 10
        menu_class = RegisterMenu

    class Button2(Button):
        order = 10
        menu_class = QRMenu

    class Button3(BaseButtonClass):
        order = 10
        menu_class = RegisterContinueMenu

    button_classes = [
        Button,
        Button2,
        Button3,
    ]

    def call_data_function(self, *args, **kwargs):
        return MainMenu(self.user).send_menu()

    def register_profile(self):
        return MainMenu(self.user).send_menu()


class PhoneAuthorization(MenuItemMixin, BaseCallData):
    """Авторизация по смс на номер телефона"""
    call_data_key = 'phoneAuthorization'
    call_data_translate = 'Авторизация'
    questions = [
        '108', '114',
    ]
    fields = {
        'phone': 'Телефон',
        'validationCode': 'Проверочный код',
        'mAppKey': None,
    }

    class Button(BaseButtonClass):
        """Кнопка в главное меню"""
        order = 0
        menu_class = MainMenu

        def check_permission(self):
            return (
                    any(map(lambda x: not self.user.get(x), profile_registration_checks)) and
                    not self.user.get('authorization')
            )

    button_classes = [
        Button
    ]

    def get_call_data_function(self, *args, **kwargs):
        """Процесс регистрации авторизации"""
        print('Процесс авторизации')

    def call_data_function(self, *args, **kwargs):
        super(PhoneAuthorization, self).call_data_function(check_user_profile=False, *args, **kwargs)

    def check_answer_addition_text(self, question, data):
        """Дополнительные действия для текста в функции check_answer_another"""
        # Проверка телефона
        if question['name'] == 'phone':
            # Проводить проверку в БД по номеру телефона
            p = validate_phone(data)
            if p is None:
                update_msg_to_user(self.user, {'text': 'Введите номер телефона в формате 7XXXXXXXXXX'})
                return data, True
            self.set_profile_field(question['name'], p)

        # Проверка кода валидации
        if question['name'] == 'validationCode':
            self.set_profile_field(question['name'], data)
            response = check_validation_code(self.user)
            if not response['successValidation']:
                text = {
                    'text': 'Введен неверный код авторизации. '
                            'Попробуйте снова или обратитесь в поддержку'
                }
                update_msg_to_user(self.user, text)
                return data, True
            self.user['authorization'] = response['successValidation']
            check_user_profile_in_db(self.user)
        return super(PhoneAuthorization, self).check_answer_addition_text(question, data)

    def update_question_text_and_buttons(self, question, question_text, buttons):
        """Запрос на код валидации перед отправкой вопроса"""
        question_text, buttons = super(PhoneAuthorization, self).update_question_text_and_buttons(
            question, question_text, buttons
        )
        if question['name'] == 'validationCode':
            # Пользователь получит validationCode
            response = send_validation_sms(self.user)
            # Только для дебага, если функция вернула в ответе проверочный код
            if 'validationCode' in response:
                question_text += f'\n\nDEBUG: Ваш проверочный код: {response["validationCode"]}'
        return question_text, buttons

    def api_function(self, request):
        """Пустой запрос при валидации номера,
        так как все необходимые запросы были сделаны ранее
        """
        return {}


class ActivateMeetupSecretary(BaseCallData):
    """Активация функционала секретаря голосования"""
    call_data_key = 'activate_meetup_secretary'
    call_data_translate = 'Активация секретаря голосования'

    def call_data_function(self, *args, **kwargs):
        self.user['secretaryActivated'] = True


class MeetupSecretaryMenuCall(BaseCallData):
    """Меню секретаря голосования"""
    call_data_key = 'meetup_secretary_menu'
    call_data_translate = 'Меню секретаря голосования'

    def call_data_function(self, *args, **kwargs):
        return MeetupSecretaryMenu(self.user).send_menu()


class ChooseMeetup(BaseCallData):
    """Выбор голосования, для которого следует зарегистрировать участников"""
    call_data_key = 'chooseMeetup'
    call_data_translate = 'Выбор Голосования'
    questions = [
        '700',
    ]
    fields = {
        'secretaryMeetupKey': 'Ключ Собрания'
    }

    def call_data_function(self, *args, **kwargs):
        return super().call_data_function(*args, check_user_profile=False, **kwargs)

    def get_call_data_function(self, *args, **kwargs):
        pass

    def api_function(self, request):
        """Никакие действия не нужны в этом случае"""
        pass


class GetMeetupParticipantBulletin(BaseCallData):
    """Регистрация участника голосования и выдача бюллетеня"""
    call_data_key = 'getMeetupParticipantBulletin'
    call_data_translate = 'Получение бюллетеня участника'
    questions = [
        '701',
        '702',
        '703',
    ]
    fields = {
        'participantPhone': 'Телефон участника',
        'participantStreet': 'Улица участника',
        'participantStreetID': 'ID улицы',
        'participantNumsite': 'Номер дома участника',
        'participantKadastrNum': 'Кадастровый номер',
        'secretaryMeetupKey': 'Ключ Собрания',
    }

    def call_data_function(self, *args, **kwargs):
        return super().call_data_function(*args, check_user_profile=False, **kwargs)

    def get_call_data_function(self, *args, **kwargs):
        pass

    def check_answer_addition_text(self, question, data):
        """Дополнительные действия для текста в функции check_answer_another"""

        # Проверка телефона
        if question['name'] == 'participantPhone':
            # Проводить проверку в БД по номеру телефона
            data = validate_phone(data)
            if data is None:
                update_msg_to_user(self.user, {'text': 'Введите номер телефона в формате 7XXXXXXXXXX'})
                return data, True
            self.set_profile_field(question['name'], data)

        elif question['name'] == 'participantStreet':
            str_id = get_street_id(
                self.user,
                {'snt': self.user.get('snt', 'sntzhd'), 'strName': data},
                raise_error=False
            )
            self.set_profile_field('participantStreetID', str_id)

        elif question['name'] == 'participantNumsite':
            response = get_kadastr_num(
                self.user,
                {'strID': self.user['participantStreetID'],
                 'strName': self.user['participantStreet'],
                 'numsite': data},
                raise_error=False
            )
            self.set_profile_field('participantKadastrNum', response.get('kadastrNum'))
        return super().check_answer_addition_text(question, data)

    def api_function(self, request):
        """Отправка запроса для получения информации"""
        voter_phone = request.pop('participantPhone')
        numsite = request.pop('participantNumsite')
        str_id = request.pop('participantStreetID')
        street = request.pop('participantStreet')
        kadastr_num = request.pop('participantKadastrNum')

        response = find_user_profile(self.user, {'phone': voter_phone, 'mAppKey': None})
        if response['userProfile']['exists']:
            voter_profile_id = response['userProfile']['profileID']
        else:
            request = {
                'name': None,
                'lastname': None,
                'grandname': None,
                'strID': str_id,
                'street': street,
                'numsite': numsite,
                'kadastrNum': kadastr_num,
                'snt': 'sntzhd',
                'phone': voter_phone,
                'isFZ152Agreed': None,
                'isRegisteredAtSNT': None,
                'saveUserData': None,
                'isValidated': None,
                'through': None,
                'mAppKey': None,
                'isDelegate': None,
                'isOwnerAtSNT': None,
                'membership': None,
                'gender': None,
            }
            response = make_post_request('registerProfileBase', request).get('response', {})
            voter_profile_id = response['profileID']

        request = {
            'profileID': self.user['profileID'],
            'meetupKey': self.user['secretaryMeetupKey'],
            'voterProfileID': voter_profile_id,
        }
        response = make_post_request('getMeetupParticipantBulletin', request).get('response', {})
        update_msg_to_user(self.user, {
            'text': 'Получены данные:\n'
                    f'kadastrNum: {kadastr_num}\n'
                    f'bulletinID: {response["bulletinID"]}\n'
                    f'votingKey: {response["votingKey"]}\n'
        })


def get_custom_classes():
    """Генератор, который возвращает список описанных в этом
    документе выше классов, с меткой __custom__ == True
    """
    for g, k in globals().copy().items():
        if getattr(k, '__custom__', False) and BaseCallData != k:
            yield k


# Коллбеки кнопок и их классы
call_data_dict = {class_.call_data_key: class_ for class_ in get_custom_classes()}
call_data_dict.update({class_.call_data_key: class_ for class_ in get_addition_custom_classes()})

# Словарь для коллбеков кнопок и их трансляции
call_data_translate_dict = {call_data_key: class_.call_data_translate
                            for call_data_key, class_ in call_data_dict.items()}
BaseCallData.call_data_translate_dict.update(call_data_translate_dict)
BaseMenu.call_data_translate_dict.update(BaseCallData.call_data_translate_dict)
BaseButtonClass.call_data_translate_dict.update(BaseCallData.call_data_translate_dict)
