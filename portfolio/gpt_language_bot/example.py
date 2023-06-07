from typing import Optional, Type

from telebot.asyncio_helper import ApiTelegramException
from telebot.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from project.core.bot import bot
from project.db.models.base import ModelManager
from project.db.models.users import UserMainState, UserModel, UserStateCb
from project.services.users import UsersService


class Route:
    """Route"""

    def __init__(self, view: Type['BaseView']):
        self.view = view
        self.value = self.view.view_name

    enum_cls = None


class Request:
    """Запрос пользователя.
    Какое-то действие пользователя упакованное в детерминированный объект.
    """

    def __init__(self, msg: Message | None = None, callback: CallbackQuery | None = None):
        self.msg = msg
        self.callback = callback
        self.__cached_user__: UserModel | None = None
        self.__cached_route__: Route | None = None

    @property
    def message(self):
        return self.msg or self.callback.message

    async def get_user(self) -> UserModel:
        if self.__cached_user__ is None:
            self.__cached_user__ = await UsersService.get_user_for_message(self.msg or self.callback)
        return self.__cached_user__

    async def get_route(self) -> Route:

        route: Route
        if self.__cached_route__ is None:
            self.__cached_route__ = RouteResolver.routes_registry.get((await self.get_user()).state.view_name)
            for route in RouteResolver.routes_registry.values():
                if await route.view.route_resolver(self, route).resolve():
                    self.__cached_route__ = route
                    break

        if self.__cached_route__ is None:
            raise RuntimeError('Route not resolved')

        return self.__cached_route__


class RouteResolver:
    """Route Resolver"""

    routes_registry: dict[str, Route] = {}

    def __init__(self, request: Request, route: Route):
        self.request = request
        self.route = route
        self.view = route.view

    async def resolve(self) -> bool:
        user = await self.request.get_user()
        if self.request.callback and self.request.callback.data in user.state.callbacks:
            cb = user.state.callbacks.get(self.request.callback.data)
            return cb is not None and cb.view_name == self.route.value
        return False

    @classmethod
    def register_route(cls, route: Route):
        cls.routes_registry[route.view.view_name] = route


class BaseMessageSender:
    """Base Message Sender"""

    keyboard_row_width = 5

    def __init__(self, view: 'BaseView'):
        self.view = view

    async def send(self):
        markup = InlineKeyboardMarkup(keyboard=await self.get_keyboard(), row_width=self.keyboard_row_width)
        user = await self.view.request.get_user()
        message = self.view.request.message
        text = await self.get_keyboard_text()
        if not text:
            return

        if self.view.edit_keyboard and user.keyboard_id is not None:
            try:
                await bot.edit_message_text(text, message.chat.id, user.keyboard_id, reply_markup=markup)
            except ApiTelegramException as err:
                if 'message to edit not found' in err.description:
                    user.keyboard_id = None
                    return await self.send()
                raise err
        else:
            if user.keyboard_id:
                try:
                    await bot.delete_message(message.chat.id, user.keyboard_id)
                except ApiTelegramException as err:
                    if (
                        'message to delete not found' in err.description
                        or "message can't be deleted for everyone" in err.description
                    ):
                        user.keyboard_id = None
                    else:
                        raise
            keyboard = await bot.send_message(message.chat.id, text, reply_markup=markup)
            user.keyboard_id = keyboard.message_id

    async def get_keyboard(self) -> list[list[InlineKeyboardButton]]:
        raise NotImplementedError

    async def get_keyboard_text(self) -> str:
        raise NotImplementedError


class ButtonsBuilder:
    """Buttons Builder"""

    def __init__(self, view: 'BaseView'):
        self.view = view

    async def btn(self, text: str, callback_data: UserStateCb) -> InlineKeyboardButton:
        user = await self.view.request.get_user()
        assert isinstance(user.state, UserMainState)
        user.state.callbacks[callback_data.id] = callback_data
        self.view.user_states.next_user_state.callbacks[callback_data.id] = callback_data
        return InlineKeyboardButton(text, callback_data=callback_data.id)

    async def view_btn(self, route: Route, index: int, **kwargs) -> InlineKeyboardButton:
        label = route.view.labels[index]
        callback_data = UserStateCb(view_name=route.view.view_name, **kwargs)
        return await self.btn(label, callback_data)


class UserStatesManager:
    """User States Manager"""

    def __init__(self, view: 'BaseView'):
        self.view = view
        self.next_user_state = UserMainState()

    async def init(self):
        self.next_user_state = UserMainState()

    async def set(self) -> None:
        user = await self.view.request.get_user()
        user.state = self.next_user_state


class CallbacksManager:
    """Callbacks Manager"""

    def __init__(self, view: 'BaseView'):
        self.view = view
        self.callback_answer = ''
        self.show_alert = True

    async def answer_callback(self) -> None:
        if self.view.request.callback:
            user = await self.view.request.get_user()
            cb = user.state.callbacks.get(self.view.request.callback.data)
            if cb is None:
                self.callback_answer = 'Keyboard Invalid'
            try:
                await bot.answer_callback_query(
                    self.view.request.callback.id,
                    self.callback_answer,
                    show_alert=self.show_alert,
                )
            except ApiTelegramException as err:
                if 'query is too old and response timeout expired or query ID is invalid' in err.description:
                    pass
                else:
                    raise err

    def set_callback_answer(self, answer: str):
        self.callback_answer = answer

    def set_show_alert(self, show_alert: bool):
        self.show_alert = show_alert


class BaseView:
    """
    Базовый вид.

    Каждый вид отображает текущее меню и состояние пользователя.
    Здесь задается заголовок и набор кнопок, которые видит пользователь.
    Нажатие на кнопку или отправка сообщения в чат приводит к какому-то действию,
    например, к переходу к другому виду, согласно паттерну.

    Когда пользователь производит какое-то действие (отправка сообщение, нажатие
    на кнопку, отправка файла, реакция), то это действие улавливается ботом через
    специальные обработчики, формируется запрос Request, который передается в
    объект текущего вида View, для обработки запроса и изменения вида.
    """

    view_name = ''
    edit_keyboard = True
    delete_income_messages = True
    page_size = 7
    labels = [
        'Базовый вид',
        'В Базовый вид',
        'Базового вида',
    ]

    route_resolver = RouteResolver
    message_sender = BaseMessageSender
    user_states_manager = UserStatesManager

    def __init__(self, request: Request, callback: UserStateCb, **kwargs):
        self.request = request
        self._callback = callback
        self.paginator = Paginator(self, self.page_size)
        self.buttons = ButtonsBuilder(self)
        self.user_states = self.user_states_manager(self)
        self.callbacks = CallbacksManager(self)
        self.__dict__.update(kwargs)

    @property
    def callback(self) -> UserStateCb:
        return self._callback

    async def dispatch(self) -> Route:
        await self.user_states.init()

        await self.message_sender(self).send()

        redirect_view = await self.redirect()
        if redirect_view is not None:
            return await redirect_view.dispatch()

        await self.callbacks.answer_callback()
        await self.user_states.set()
        if self.request.msg and self.delete_income_messages:
            await bot.delete_message(self.request.message.chat.id, self.request.message.message_id)
        return self.route_resolver.routes_registry[self.view_name]

    async def redirect(self) -> Optional['BaseView']:
        return None


class Paginator:
    """Paginator for View"""

    def __init__(self, view: BaseView, page_size: int):
        self.view = view
        self.page_size = page_size

    async def paginate(self, manager: ModelManager, page_num: int, **kwargs):
        return await manager.find_all(
            **kwargs,
            sort=[('_id', 1)],
            limit=self.page_size,
            skip=(page_num - 1) * self.page_size,
        )

    async def get_pagination(self, total: int, page_num: int, **kwargs) -> list[list[InlineKeyboardButton]]:
        page_num = int(page_num)
        r = self.view.route_resolver.routes_registry
        route = r[self.view.view_name]

        pages = total // self.page_size
        if total / self.page_size > pages:
            pages += 1

        def page_label(num: int):
            if num == page_num:
                return f'-{num}-'
            return str(num)

        pages_info = [[]]
        if pages <= 1:
            pages_info.clear()

        elif 1 < pages < 7:

            for i in range(pages):
                callback = UserStateCb(view_name=route.value, page_num=i + 1, **kwargs)
                pages_info[0].append(await self.view.buttons.btn(page_label(i + 1), callback))

        elif pages >= 7 and page_num < 5:
            #   .
            # ['1', '2', '3', '4', '5', '>>', '99']
            #        .
            # ['1', '2', '3', '4', '5', '>>', '99']
            #             .
            # ['1', '2', '3', '4', '5', '>>', '99']
            #                  .
            # ['1', '2', '3', '4', '5', '>>', '99']

            for i in range(5):
                callback = UserStateCb(view_name=route.value, page_num=i + 1, **kwargs)
                pages_info[0].append(await self.view.buttons.btn(page_label(i + 1), callback))

            callback = UserStateCb(view_name=route.value, page_num=pages, **kwargs)
            pages_info[0].append(await self.view.buttons.btn('>>', callback))
            pages_info[0].append(await self.view.buttons.btn(page_label(pages), callback))

        elif pages >= 7 and page_num > pages - 4:
            #                    .
            # ['1', '<<', '95', '96', '97', '98', '99']
            #                          .
            # ['1', '<<', '95', '96', '97', '98', '99']
            #                                .
            # ['1', '<<', '95', '96', '97', '98', '99']
            #                                      .
            # ['1', '<<', '95', '96', '97', '98', '99']

            callback = UserStateCb(view_name=route.value, page_num=1, **kwargs)
            pages_info[0].append(await self.view.buttons.btn(page_label(1), callback))
            pages_info[0].append(await self.view.buttons.btn('<<', callback))

            for i in range(pages - 5, pages):
                callback = UserStateCb(view_name=route.value, page_num=i + 1, **kwargs)
                pages_info[0].append(await self.view.buttons.btn(page_label(i + 1), callback))
        elif pages >= 7:
            #                   .
            # ['1', '<<', '6', '7', '8', '>>', '99']
            #                    .
            # ['1', '<<', '94', '95', '96', '>>', '99']

            callback = UserStateCb(view_name=route.value, page_num=1, **kwargs)
            pages_info[0].append(await self.view.buttons.btn(page_label(1), callback))
            pages_info[0].append(await self.view.buttons.btn('<<', callback))

            callback = UserStateCb(view_name=route.value, page_num=page_num - 1, **kwargs)
            pages_info[0].append(await self.view.buttons.btn(page_label(page_num - 1), callback))

            callback = UserStateCb(view_name=route.value, page_num=page_num, **kwargs)
            pages_info[0].append(await self.view.buttons.btn(page_label(page_num), callback))

            callback = UserStateCb(view_name=route.value, page_num=page_num + 1, **kwargs)
            pages_info[0].append(await self.view.buttons.btn(page_label(page_num + 1), callback))

            callback = UserStateCb(view_name=route.value, page_num=pages, **kwargs)
            pages_info[0].append(await self.view.buttons.btn('>>', callback))
            pages_info[0].append(await self.view.buttons.btn(page_label(pages), callback))

        return pages_info
