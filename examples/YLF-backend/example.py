"""
Модуль для яндекс функции
Функции API для работы с данными пользователей-делегатов
"""

import base64

from autodoc.decorators import api_function_decorator
from utils.regex_utils import validate_phone
from utils.snt import get_snt
from src.DelegateMeetupObjects import (
    DelegateMeetup,
    DelegateMeetupBulletin,
    DelegateMeetupBulletinPDF,
)
from src.UserObjects import User
from utils.exceptions import (
    APIResponseError,
    BotMessageError,
    BulletinVoterIdIncorrect,
    CannotVoteForYourSelf,
)
from utils.mongodb_utils import (
    db,
    get_next_sequence_index,
)
from utils.check_utils import (
    check_request_fields,
    check_request_fields_batch,
    check_user,
    check_meetup,
    check_meetup_bulletin,
    check_user_by_field,
)


@check_request_fields(['profileID'])
@check_user()
@api_function_decorator
def register_profile_delegate(body):
    """registerProfileDelegate
    Регистрация пользователя как делегата.

    Отмечает пользователя с полученным profileID делегатом.
    Генерирует и возвращает delegateID.
    Генерирует документ голосования в коллекции meetup

    UPD: Происходит предварительный поиск делегата для пользователя.
         Предварительно удаляются все голосования для делегата.
         Бюллетени больше не генерируются заранее.

    POST request
    ```
    "function": "registerProfileDelegate",
    "request": {
        "profileID": "<profile-id>",
    }
    ```

    Response
    ```
    "Reply": "Ok",
    "function": "registerProfileDelegate",
    "response": {
        "delegateID": "<delegate-id>",
        "_id": "<id-in-db>"
    }
    ```
    """

    profile_id = body['request']['profileID']
    user = User.load_from_db(
        fields_to_pull=[
            '_id',
            'profileID',
            'lastname',
            'name',
            'grandname',
            'street',
            'delegate',
            'isDelegate',
        ],
        **{'profileID': profile_id}
    )

    if not user.get('isDelegate'):
        raise APIResponseError('User cannot be a delegate')

    # Проверка существующего делегата
    if 'delegate' not in user:
        # Поиск существующей записи делегата для пользователя
        delegate = db.delegate.find_one({'user.profileID': profile_id}, ['delegateID', 'user'])
        if delegate is None:
            # Генерация идентификатора для делегата
            delegate_id = get_delegate_id()
            delegate = {'delegateID': delegate_id,
                        'user': {'profileID': profile_id, '_id': user['_id']}}
            # Создаем запись в коллекции делегатов
            db.delegate.insert_one(delegate)

        # Поиск и удаление существующих записей голосования для делегата
        DelegateMeetup.delete_meetups(**{'delegateID': delegate['delegateID']})

        # Создаем meetup для делегата по шаблону
        # meetup = Meetup(delegate)
        meetup = DelegateMeetup()
        # Заполнение шаблона голосования
        meetup.fill_template(user, delegate)
        # Сохранение нового голосования в БД
        meetup.insert_to_db()

        # Обновляем пользователя
        user.update_to_db(
            query={'$set': {
                'isDelegate': True,
                'delegate': {'delegateID': delegate['delegateID'],
                             '_id': delegate['_id']}
            }},
            **{'profileID': profile_id}
        )
    else:
        delegate = user['delegate']
    return {'response': {'delegateID': delegate['delegateID'], '_id': str(delegate['_id'])}}


@api_function_decorator
def get_delegate_list(body):
    """getDelegateList
    Функция для запроса списка делегатов

    GET request
    ```
    ?function=getDelegateList
    ```

    POST request
    ```
    "function": "getDelegateList"
    "request": {
        "delegateID": 'asdasdasd',  # unnececary parameter, to get only one delegate
    }
    ```

    Response
    ```
    "Reply": "Ok",
    "function": "getDelegateList",
    "response": {
        "delegateList": [
            {
                "delegateID":'{{objectId()}}',
                "full_name_string": "Фамилия И. О., ул. Малинная, количество доверителей: 0",
                "name": 'Фамилия И. О.',
                "street": 'Малинная',
                "strID":'{{street()}}',
                "about":'{{lorem(2)}}',
                "url": "http://placehold.it/32x32",
                "principials":[{"bulletinID": "hfhfhsj", "voterID": "dfdgd", "timestamp": "1-2-3-12-20"}, ...],
                "principialsQuantity":"",
                "notaryPrincipialsQuantity":""
            },
            ...
        ]
    }
    ```
    """
    d_id = body.get('request', {}).get('delegateID')  # Необязательный параметр
    d_filter = (
        {'isDelegate': True, 'delegate.delegateID': d_id}
        if d_id else
        {'isDelegate': True, 'delegate': {'$exists': True}}
    )
    if db.users.count_documents(d_filter) == 0:
        raise APIResponseError('There is no delegates')
    delegates = db.users.find(d_filter, ['delegate', 'strID', 'name', 'lastname',
                                         'grandname', 'street', 'phone', 'gender'])

    delegate_list = []
    for d in delegates:
        # principials, quantity, notary_quantity = get_delegate_principials(d)
        principials = quantity = notary_quantity = None
        full_name_string = f'{d["lastname"]} {d["name"]} {d["grandname"]}, {d["street"]}'
        if quantity:
            full_name_string += f', количество доверителей: {quantity}'
        delegate_list.append({
            'delegateID': d['delegate']['delegateID'],
            'fullNameString': full_name_string,
            'name': f'{d["lastname"]} {d["name"][0]}. {d["grandname"][0]}.',
            'gender': d.get('gender'),
            'street': d['street'],
            'strID': d['strID'],
            'phone': d['phone'],
            'about': '',
            'url': '',
            'principials': principials,
            'principialsQuantity': quantity,
            'notaryPrincipialsQuantity': notary_quantity,
            'coordinates': d['delegate'].get('coordinates', [45.0637, 39.2193])
        })

    return {'response': {'delegateList': delegate_list}}


@api_function_decorator
def get_delegates_map(body):
    """getDelegatesMap
    Возвращает список делегатов в формате, пригодном для отображения их на карте audit.snt

    GET request
    ```
    ?function=getDelegatesMap
    ```

    POST request
    ```
    "function": "getDelegatesMap"
    ```

    Response
    ```
    "Reply": "Ok",
    "function": "getDelegatesMap",
    "response": {
        "features": [
            {
                "geometry": {
                    "coordinates": [45.0637, 39.2193],
                    "type": "Point"
                },
                "properties": {
                    "about": "",
                    "fullNameString": "Нижниковская Е. А., ул. Вишневая, количество доверителей: 0",
                    "phone": "9184428303",
                    <...>
                },
                "type": "Feature"
            },
            <...>
        ]
    }
    ```
    """
    delegate_list = get_delegate_list(body)['response']['delegateList']
    features = []
    for delegate in delegate_list:
        delegate.update({
            'marker-color': '#7e877d',
            'marker-size': 'medium',
            'marker-symbol': '',
            'hintContent': 'hintContent',
            'balloonContent': 'balloonContent',
            'iconContent': 'iconContent',
            'iconLayout': 'default#image',
            'iconImageHref': 'https://www.pinclipart.com/picdir/big/410-4103152_shy-student-clipart.png',
            'iconImageSize': [30, 30],
            'preset': 'islands#blackStretchyIcon'
        })
        features.append({
            'type': 'Feature',
            'properties': delegate,
            'geometry': {
                'type': 'Point',
                'coordinates': delegate['coordinates']
            }
        })
    return {'response': {'features': features}}


@check_request_fields_batch(['profileID', 'mAppKey', 'delegateID'])
@check_user_by_field('profileID')
@check_user_by_field('delegateID', 'delegate.delegateID')
@check_meetup()
@api_function_decorator
def get_delegate_question(body):
    """getDelegateQuestion
    Возвращает вопрос из повестки голосования за делегата

    POST request
    ```
    "function": "getDelegateQuestion"
    "request": {
        "profileID": "<profileID>",
        "mAppKey": "<mAppKey>",
        "delegateID": "<delegateID>"
    }
    ```

    Response
    ```
    "Reply": "Ok",
    "function": "getDelegateQuestion",
    "response": {
        "Кандидат": "<Кандидат>",
        "Идентификационный номер кандидата": "<Идентификационный номер кандидата>",
        "Условия Голосования": {
            "Юридические Основания": "<Юридические Основания>",
            "Кто имеет право голоса": "<Кто имеет право голоса>",
            "Вопрос": "<Вопрос>",
            "Текст Доверенности": "<Текст Доверенности>",
            "Ссылка на Документ": "<Ссылка на Документ>",
            "Варианты Ответа": "<Варианты Ответа>",
        }
    }
    ```
    """
    profile_id = body['request']['profileID']
    delegate_id = body['request']['delegateID']

    # Поиск голосующего пользователя
    voter_user = db.users.find_one(
        {'profileID': profile_id},
        [
            'delegate',
        ]
    )

    if voter_user.get('delegate', {}).get('delegateID') == delegate_id:
        raise CannotVoteForYourSelf

    # Голосование для делегата
    # meetup = Meetup.load_meetup_from_db({'delegateID': delegate_id})
    meetup = DelegateMeetup.load_from_db(**{'delegateID': delegate_id})
    return {'response': {
        'Кандидат': meetup['Кандидат'],
        'Идентификационный номер кандидата': meetup['Идентификационный номер кандидата'],
        'Условия Голосования': meetup['Условия Голосования'],
    }}


@check_request_fields_batch(['profileID', 'mAppKey', 'delegateID'])
@check_user_by_field('profileID')
@check_user_by_field('delegateID', 'delegate.delegateID')
@check_meetup()
@api_function_decorator
def get_delegate_bulletin(body):
    """getDelegateBulletin
    Выдает бюллетень для голосвания
    Генерирует бюллетень из шаблона. Связывает его с голосованием.

    POST request
    ```
    "function": "getDelegateBulletin"
    "request": {
        "profileID": "<profileID>",
        "mAppKey": "<mAppKey>",
        "delegateID": "<delegateID>"
    }
    ```

    Response
    ```
    "Reply": "Ok",
    "function": "getDelegateBulletin",
    "response": {
        "bulletinID": "<bulletinID>",
        "conditions": {
            "Варианты Ответа": [],
            "Вопрос": "<Вопрос>",
        },
        "links": {
            "Ссылка на печать": "<Ссылка на печать>",
            "Ссылка на скан заполненного бюллетеня": "<Ссылка на скан заполненного бюллетеня>",
            "Ссылка на электронный бюллетень": "<Ссылка на электронный бюллетень>"
        },
        "voterID": "<voterID>",
        "voterRight": "<voterRight>"
    }
    ```
    """
    profile_id = body['request']['profileID']  # ID голосующего (принципиала)
    delegate_id = body['request']['delegateID']
    response = {}  # Ответ из функции будет записан в этот словарь

    # Поиск голосующего пользователя
    voter_user = User.load_from_db(
        fields_to_pull=[
            'phone',
            'profileID',
            'lastname',
            'name',
            'grandname',
            'street',
            'delegate',
            'kadastrNum',
            'street',
            'isValidated',
            'isRegisteredAtSNT',
            'isOwnerAtSNT',
            'membership',  # isMembershipOfSNT
            'snt',
        ],
        **{'profileID': profile_id}
    )

    delegate_user = User.load_from_db(
        fields_to_pull=[
            'profileID',
            'lastname',
            'name',
            'grandname',
            'street',
            'delegate',
            'snt',
        ],
        **{'delegate.delegateID': body['request']['delegateID']}
    )

    if 'snt' in voter_user and voter_user['snt'] != delegate_user.get('snt'):
        raise APIResponseError('Нельзя голосовать за делегата из другого СНТ')

    if voter_user.get('profileID') == delegate_user.get('profileID'):
        raise CannotVoteForYourSelf

    # Проверка на валидацию номера
    # voter_user.check_validation()
    # if not voter_user.get('isValidated'):
    #     raise UserNotValidated(response={'profileID': voter_user['profileID']})

    # Генерируем votingKey, voter_id, voter_right
    # voter_id = get_voter_id(voter_user)
    # voter_id = voter_user.get_voter_id()

    # Поиск существующего бюллетеня
    bulletin = DelegateMeetupBulletin.load_from_db(
        raise_exception=False,
        **{
            'delegateID': delegate_id,
            '$or': [{'profileID': voter_user['profileID']},
                    {'Идентификатор избирателя': voter_user.voter_id}]
        }
    )
    # if bulletin is not None:
    #     raise APIResponseError('This voter has already had bulletin for that delegate',
    #                            {'voterID': voter_id, 'delegateID': delegate_id})

    # Если бюллетень еще не создавался
    created = False
    if not bulletin:
        created = True

        # Голосование для делегата
        meetup = DelegateMeetup.load_from_db(**{'delegateID': delegate_id})

        # Генерируем бюллетень
        bulletin = DelegateMeetupBulletin()
        bulletin.assign_meetup(meetup)
        bulletin.append_bulletin_protocol('Новый бюллетень создан')

        # Заполняем шаблон
        bulletin.fill_template(delegate_user, voter_user)
        meetup.add_bulletin_created(bulletin)  # Бюллетени созданы
        meetup.add_bulletin_given(bulletin)  # Бюллетени выданы

        # Если у пользователя не заполнен СНТ, то добавить бюллетень в список условных
        if 'snt' not in voter_user:
            meetup.add_bulletin_conditional(bulletin)
            bulletin['Проверка прав избирателя'] = False

    bulletin.check_done()
    answered = bulletin.check_answer(None, raise_exc=False)

    bulletin.append_bulletin_protocol('Избиратель запросил бюллетень электронно')

    # Генерируем votingKey, voter_right
    voting_key = bulletin.generate_voting_key(6)
    # voter_right = get_voter_right(voter_user)

    voter_user.update_to_db(
        query={'$set': {'voterRight': voter_user.voter_right}},
        # **{'profileID': voter_user['profileID']}
    )
    # db.users.update_one(
    #     {'profileID': voter_user['profileID']},
    #     {'$set': {'voterRight': voter_user.voter_right}}
    # )

    # Сохранение нового кода для голосования в бюллетень
    bulletin.save_voting_key_to_bulletin(voting_key)

    # Отправка СМС сообщения и PUSH уведомления
    try:
        bulletin.send_voting_key_sms(voter_user)
    except BotMessageError:
        pass
        # response['votingKey'] = voting_key

    bulletin.append_bulletin_protocol('Код Подтверждения направлен избирателю по смс '
                                      f'на телефон, указанный при регистрации')

    # Связываем голосование с бюллетенем
    bulletin.append_bulletin_protocol('Бюллетень выдан избирателю')

    # Сохраняем бюллетень в БД в отдельной коллекции
    if created:
        bulletin.insert_to_db()
    else:
        bulletin.update_to_db()

    response.update({
        'bulletinID': bulletin['Идентификатор Бюллетеня'],
        'voterID': voter_user.voter_id,
        'voterRight': voter_user.voter_right,
        'conditions': {
            'Вопрос': bulletin['Условия Голосования']['Вопрос'],
            'Варианты Ответа': bulletin['Условия Голосования']['Варианты Ответа'],
        },
        'links': bulletin['Ссылки'],
        'answered': answered,
        'detail': bulletin.get_public_detail()
    })

    return {'response': response}


@check_request_fields_batch(['profileID', 'mAppKey', 'bulletinID', 'answer', 'transferMethod'])
@check_user()
@check_meetup_bulletin()
@api_function_decorator
def answer_delegate_bulletin(body):
    """answerDelegateBulletin
    Подписание бюллетеня по голосованию за делегата. Сохранение ответа.

    POST request
    ```
    "function": "answerDelegateBulletin"
    "request": {
        "profileID": "<profileID>",
        "mAppKey": "<mAppKey>",
        "bulletinID": "<bulletinID>",
        "answer": "За",  # one of ["За", "Против", "Воздержался"] from meetup bulletin conditions
        "transferMethod": "Телеграм",  # one of ["на бумажном носителе", "смс", "приложение", "телеграм"] from meetup bulletin conditions
    }
    ```

    Response
    ```
    "Reply": "Ok",
    "function": "answerDelegateBulletin"
    ```
    """

    # Ищем бюллетень для голосования в БД
    # bulletin = MeetupBulletin.load_bulletin_from_db(bulletin_id=body['request']['bulletinID'])
    bulletin = DelegateMeetupBulletin.load_from_db(
        **{'Идентификатор Бюллетеня': body['request']['bulletinID']}
    )
    bulletin.check_done()
    bulletin.check_answer(None)

    # Ищем голосование для делегата в БД
    # meetup = Meetup.load_meetup_from_db({'delegateID': bulletin['delegateID']})
    meetup = DelegateMeetup.load_from_db(**{'delegateID': bulletin['delegateID']})

    bulletin.add_answer(body['request']['answer'], None)
    bulletin.add_transfer_method(body['request']['transferMethod'], None)

    # Сохранение текущего состояния бюллетеня
    bulletin.update_to_db()
    # Сохранение текущего состояния голосования
    meetup.update_to_db()
    return {}


@check_request_fields_batch(['profileID', 'mAppKey', 'bulletinID', 'votingKey', 'voterID'])
@check_user()
@check_meetup_bulletin()
@api_function_decorator
def confirm_delegate_bulletin(body):
    """confirmDelegateBulletin
    Подтверждение своего голоса, используя votingKey

    POST request
    ```
    "function": "confirmDelegateBulletin"
    "request": {
        "profileID": "<profileID>",
        "mAppKey": "<mAppKey>",
        "bulletinID": "<bulletinID>",
        "votingKey": "142736",
        "voterID": "4567",
    }
    ```

    Response
    ```
    "Reply": "Ok",
    "function": "confirmDelegateBulletin"
    ```
    """
    bulletin = DelegateMeetupBulletin.load_from_db(**{'Идентификатор Бюллетеня': body['request']['bulletinID']})
    bulletin.check_done()
    bulletin.check_confirmation()

    if body['request']['voterID'] != bulletin['Идентификатор избирателя']:
        raise BulletinVoterIdIncorrect(response={'voterID': body['request']['voterID']})

    # Ищем голосование для делегата в БД
    meetup = DelegateMeetup.load_from_db(**{'delegateID': bulletin['delegateID']})

    voting_key = str(body['request']['votingKey'])
    voter_id = str(body['request']['voterID'])

    voter_user = User.load_from_db(
        fields_to_pull=[
            'phone',
            'profileID',
            'lastname',
            'name',
            'grandname',
            'street',
            'delegate',
            'kadastrNum',
            'street',
            'isValidated',
            'isRegisteredAtSNT',
            'isOwnerAtSNT',
            'membership',  # isMembershipOfSNT
        ],
        **{'profileID': body['request']['profileID']}
    )
    if voter_user.voter_id != voter_id:
        raise BulletinVoterIdIncorrect

    delegate_user = User.load_from_db(
        fields_to_pull=[
            'profileID',
            'lastname',
            'name',
            'grandname',
            'street',
            'delegate',
        ],
        **{'delegate.delegateID': bulletin['delegateID']}
    )

    # Проверка кода подтверждения
    bulletin.check_voting_key(body['request']['votingKey'])
    # Добавление итоговой записи
    bulletin.add_result_record(delegate_user, voter_user, voting_key)
    bulletin.add_public_result_record(voter_user, voting_key)

    # Добавление итоговой записи в голосование
    meetup.append_bulletin_result_to_protocol(bulletin)
    meetup.append_bulletin_result_to_public_protocol(bulletin)

    # Завершение бюллетеня
    bulletin.make_bulletin_done()
    # Сохранение текущего состояния бюллетеня
    bulletin.update_to_db()
    # Сохранение текущего состояния голосования

    meetup.add_bulletin_returned(bulletin)  # Бюллетени возвращены
    # meetup.update_to_db()
    return {}


# @check_request_fields_batch(['profileID', 'mAppKey', 'bulletinID'])
# @check_user()
@check_request_fields_batch(['bulletinID'])
@check_meetup_bulletin()
@api_function_decorator
def get_delegate_bulletin_pdf(body):
    """getDelegateBulletinPDF
    Получение бюллетеня как PDF документа

    GET request
    ```
    ?function=getDelegateBulletinPDF
    &bulletinID=<bulletinID>
    ```

    POST request
    ```
    "function": "getDelegateBulletinPDF"
    "request": {
        "bulletinID": "<bulletinID>"
    }
    ```

    Response
    ```
    <base64-encoded-pdf-file>
    ```
    """
    bulletin = DelegateMeetupBulletin.load_from_db(**{'Идентификатор Бюллетеня': body['request']['bulletinID']})
    meetup = DelegateMeetup.load_from_db(**{'delegateID': bulletin['delegateID']})
    pdf_content = DelegateMeetupBulletinPDF().make_meetup_bulletin_pdf(meetup, bulletin)
    b64_data = base64.b64encode(pdf_content.encode("latin1")).decode()
    return {'response': b64_data, 'Content-Type': 'application/pdf'}


@check_request_fields_batch(['phone', 'delegateID'])
@api_function_decorator
def web_voting_for_delegate(body):
    """webVoting4Delegate
    Пока что функция заглушка для голосования за делегата на фронтенде

    POST request
    ```
    "function": "webVoting4Delegate"
    "request": {
        "phone": "9586586586",
        "delegateID": "5ebfe734e327bf8caa19dde6",
    }
    ```

    Response
    ```
    "Reply": "Ok",
    "function": "webVoting4Delegate",
    "response": {
        "answer": "Сообщение 1"
    }
    ```
    """
    phone = validate_phone(str(body['request']['phone']), raise_exception=True)
    if db.users.count_documents({'phone': phone}) == 1:
        return {'response': {'answer': 'Сообщение 1'}}
    return {'response': {'answer': 'Сообщение 2'}}


#######################################################################################################################


def get_delegate_principials(d):
    """Формирует список принципиалов для делегата"""
    notary_quantitiy = 0  # Это пока не понятно откуда брать
    meetup = db.meetup.find_one(
        {
            'delegateID': d['delegate']['delegateID']
        },
        [
            'register.answer.voterID',
            'register.answer.bulletinID',
            'register.answer.timestamp'
        ]
    )
    return meetup['ПротоколГолосования'], len(meetup['ПротоколГолосования']), notary_quantitiy


def get_delegate_id() -> str:
    """Генерация ID для делегата в виде 0883-N"""
    snt = get_snt('sntzhd')
    inn = snt['PayeeINN']
    inn_4_8 = inn[4:8]

    delegate_number = get_next_sequence_index('delegate_number')
    return f'{inn_4_8}-{delegate_number:0>3}'  # 0883-00N

