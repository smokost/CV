"""
Отрывок кода из парсера
"""


class Parser:
    """
    Класс для парсинга эвентов
    """

    def __init__(self):
        self._driver: webdriver.Chrome = None
        self._driver_current_proxy = None
        self.authorized = False

        self._event_list = []
        self._collected_data_to_sheet = []
        self._collected_data = []

        self.pproxy = MyPproxy(_proxies)
        self.pproxy.run_server_in_thread()

    def _get_driver(self):
        """Возвращает объект драйвера для браузера"""

        try:
            # self._driver.close()
            self._driver.quit()
            self._driver = None
            logger.info('Старый драйвер закрыт')
        except:
            logger.info('Новый драйвер')
            pass

        self._driver: webdriver.Chrome = webdriver.Chrome(
            cfg['PARSER'].get('chromedriver_path') or './chromedriver',
            chrome_options=chrome_options
        )
        self._driver.set_page_load_timeout(30)
        self._driver.set_script_timeout(30)

        # Получаем ID расширения с прокси self._proxy_extension_id
        # self._driver_get_proxy_extension_id()

    @property
    def driver(self) -> webdriver.Chrome:
        if self._driver is None:
            self._get_driver()
        return self._driver

    def _go_parse(self):
        """Процесс парсинга фейсбука"""
        # Авторизация
        # С авторизацией возникают блокировки со стороны фейсбука
        # self._driver_authorize()

        logger.info('Собираем предстоящие эвенты. Заполняется список self._event_list')
        self._get_event_list()

        # Сохраняем промежуточные данные для дебага
        with open('_event_list.json', 'w') as _f:
            json.dump(self._event_list, _f, ensure_ascii=False, indent=1)

        logger.info('Обработка полученного списка эвентов')
        self._process_event_list()

        # Сохраняем промежуточные данные для дебага
        with open('_collected_data.json', 'w') as _f:
            json.dump(self._collected_data, _f, ensure_ascii=False, indent=1)
        return

    def go_parse(self):
        """Процесс парсинга фейсбука"""
        try:
            # Выполнение парсинга
            self._go_parse()
        finally:
            # Правильное закрытие браузера
            self.driver.quit()

        # Очистка таблицы от старых строк
        self._delete_old_rows()

    def _driver_authorize(self):
        """Авторизация на фейсбуке"""
        logger.info('Авторизация')
        self._driver_authorize_by_cookie()
        if not self.authorized:
            self._driver_authorize_by_login_and_password()

        self.driver.save_screenshot(os.path.join(screenshots_path, 'auth.png'))
        logger.info('Конец авторизации')

        # Сохраняем обновленные куки
        cookies = self.driver.get_cookies()
        with open('cookie.json', 'w') as f:
            json.dump(cookies, f, indent=1)

    def _driver_accept_cookies(self):
        """Принять файлы куки на сайте"""
        xpath = '//div[@id="cookie_banner_title"]/div[@id="consent_cookies_title"]'
        cookie = self.driver.find_elements_by_xpath(xpath)
        if cookie:
            # logger.debug('Принимаем файлы куки')
            xpath2 = '//button[@data-testid="cookie-policy-dialog-accept-button"]'
            btns = self.driver.find_elements_by_xpath(xpath2)
            for btn in btns:
                btn.click()
                break

    def _driver_check_authorize_result(self):
        """Проверка удачной авторизации"""

        self._driver_get('https://www.facebook.com/')

        # Проверка, что авторизация через куки успешна
        self.driver.find_element_by_xpath('//a[@href="/"]')
        self.driver.find_element_by_xpath('//a[@href="/friends/"]')
        self.driver.find_element_by_xpath('//a[@href="/groups/"]')
        self.authorized = True

    def _driver_handle_exceptions(self, func, args=(), kwargs=None):
        """Обработчик ошибок от браузера"""
        exception = None
        result = None

        kwargs = kwargs or {}
        try:
            result = func(*args, **kwargs)
        except (WebDriverException, ParserException) as err:
            str_err_lower = str(err).lower()
            logger.warning('Ошибка в момент итерации: ' + str_err_lower)
            check_error = (
                    'chrome not reachable' in str_err_lower or
                    'session deleted because of page crash' in str_err_lower or
                    'invalid session id' in str_err_lower
            )
            check_error_2 = 'timed out receiving message from renderer' in str_err_lower
            check_error_3 = (
                    isinstance(err, ShouldBeReloadedException) and
                    'need to reload' in str_err_lower
            )
            exception = err
            if check_error or check_error_2:
                self._get_driver()
            # elif check_error_2:
            #     pass
            # self.pproxy.delete_actual_proxy(f'{str_err_lower} {self.pproxy.alive_server.bind}')
            elif check_error_3:
                pass
            else:
                raise err
        return exception, result

    def _driver_set_random_proxy(self):
        """Установка рандомного прокси из списка"""
        # Открываем новое окно, закрываем старое
        self.driver.execute_script('window.open();')
        while len(self.driver.window_handles) > 1:
            self.driver.close()

        self.pproxy.change_proxy()

        self.driver.switch_to.window(self.driver.window_handles[0])

    def _get_event_list(self):
        """Пробегается по списку ссылок на группы и собирает ссылки на предстоящие эвенты"""
        self._event_list.clear()
        list_len = len(list_of_links)

        # Итерация по всем элементам, кроме первого
        i = 1
        while i < list_len:
            group_link = list_of_links[i]
            location_name = list_of_locations[i]
            logger.info(f'{group_link} {location_name}\n')

            # Получение списка событий со страницы группы
            exception, result = self._driver_handle_exceptions(
                self._get_event_list_from_group,
                (group_link, i)
            )

            # Если была ошибка, то пытаемся обработать
            # снова ту же страницу
            if exception is None:
                logger.info(
                    f'Страница {i} из {list_len}\n'
                    f'Найдено эвентов: {len(result)}'
                )
                if result:
                    # location_name, event_list
                    self._event_list.append((location_name, result))
                    for index, r in enumerate(result):
                        logger.debug(f'{index} {r}')
                i += 1

    def _get_event_list_from_group(self, group_link, link_i_, retry=0):
        """Получает список эвентов с группы"""

        # Устанавливаем рандомный прокси
        self._driver_set_random_proxy()

        self.driver.delete_all_cookies()
        self._driver_get(group_link)
        self._driver_accept_cookies()
        event_links = []

        # Ждем прогресс бар пять секунд
        timer = time.monotonic()
        loader = [True]
        while loader:
            loader = self.driver.find_elements_by_xpath('//div[@id="page-events-tab-loading-spinner"]')
            if time.monotonic() - timer > 5:
                break
            time.sleep(1)

        # Проверка прав на этой странице: она может быть заблокирована, закрыта, удалена и т.д.
        permitted = False
        for check in check_permissions_list:
            permitted = self.driver.find_elements_by_xpath(check['xpath'])
            if permitted:
                logger.info(check['info'])
                if check.get('retry') and retry < 2:
                    retry = retry + 1
                    logger.info(f'Попытка с другим прокси: {retry}')
                    return self._get_event_list_from_group(group_link, link_i_, retry=retry)
                break

        # Делаем скриншот страницы
        self.driver.save_screenshot(os.path.join(screenshots_path, f'group{link_i_:0>4}.png'))

        if not permitted:
            # Поиск эвентов
            event_links = self._get_groups_event_links()

        return event_links

    def _get_groups_event_links(self):
        """Получение списка предстоящих эвентов группы"""

        event_links = set()
        # Находим все ссылки на эвенты
        first_links = self.driver.find_elements_by_xpath(
            '//span/a'
            '[contains(@href, "/events/")]'
            '[contains(@href, "/?acontext")]'
            '[not(contains(@href, "dates"))]'
        )

        event_links.update({link.get_attribute('href').split('?')[0] for link in first_links})

        # Находим все диалоги с расписанием
        dialogs = self.driver.find_elements_by_xpath(
            '//a[contains(@href, "/events/")][contains(@href, "/dates/?acontext")]'
        )

        # Кликаем по каждому диалогу и парсим еще список ссылок
        for dialog in dialogs:
            try:
                dialog.click()
            except:
                self.driver.execute_script('arguments[0].click();', dialog)
            time.sleep(1)

        # Парсим все эвенты
        dialog_links = self.driver.find_elements_by_xpath(
            '//a[contains(@href, "/events/")]'
            '[contains(@href, "/?event_time_id=")]'
            '[contains(@href, "&acontext=")]'
        )
        for link in dialog_links:
            link = re.sub(
                r'https?://(www.|)facebook.com/events/(\d*)/\?event_time_id=(\d*)&.*',
                r'https://www.facebook.com/events/\3/',
                link.get_attribute('href'),
                flags=re.I
            )
            event_links.add(link)

        return list(event_links)

    def _process_event_list(self):
        """Обработка списка эвентов self._event_list"""
        # now = datetime.now()
        index = -1
        total_counter = -1
        self.need_to_change_proxy = False
        for location_name, event_links in self._event_list:
            index += 1
            i = 0
            event_links_len = len(event_links)
            logger.debug(f'Обработка эвентов от "{location_name}"')

            counter = 0
            while i < event_links_len:
                total_counter += 1
                if total_counter % 10 == 0:
                    self.need_to_change_proxy = True
                # for event_link in event_links:
                event_link = event_links[i]

                exception = result = None
                if counter < 3:
                    logger.debug(f'Обработка эвента {total_counter} {index} {i} {event_link} {counter}')

                    def _process():
                        # Устанавливаем рандомный прокси
                        if self.need_to_change_proxy:
                            self._driver_set_random_proxy()
                            self.need_to_change_proxy = False
                        self._process_event_link(event_link, location_name)
                        self.driver.save_screenshot(os.path.join(screenshots_path, f'event{index:0>4}_{i:0>4}.png'))

                    exception, result = self._driver_handle_exceptions(
                        _process,
                    )

                counter += 1
                if exception is None:
                    i += 1
                    counter = 0

            # Отправка накопленных данных для каждой локации с эвентами
            self._send_collected_data()

    def _collect_data(self, name_, date1_, time1_, date2_, time2_, descr_, tag_, url_, loc_, sen_, ref_='parser'):
        """Записывает строку в self._collected_data"""
        new_row = [''] * len(whole_table1[0])

        new_row[name] = name_
        new_row[description] = descr_
        new_row[date1] = date1_
        new_row[time1] = time1_
        new_row[date2] = date2_
        new_row[time2] = time2_
        new_row[location] = loc_
        new_row[category] = tag_
        new_row[url] = url_
        new_row[sended] = sen_
        new_row[referer] = ref_

        # sheet1.insert_row(new_row, 2)
        if new_row not in self._collected_data_to_sheet:
            self._collected_data_to_sheet.append(new_row)
            whole_table1.insert(2, new_row)
            sheet1_url_values.append(new_row[url])
            logger.debug(f'Будет отправлено в таблицу: {url_}')

    def _send_collected_data(self):
        """Отправка накопленных данных в таблицу"""
        if self._collected_data_to_sheet:
            sended_rows = 'Отправлено строк: ' + str(len(self._collected_data_to_sheet))
            logger.info(sended_rows)
            sheet1.insert_rows(self._collected_data_to_sheet[::-1], 2)
            # table_worker.add_task(sheet1.insert_rows, (collected_data.copy()[::-1], 2), sended_rows)
            self._collected_data_to_sheet.clear()

    def _delete_old_rows(self):
        """Удаление устаревших записей в таблице"""
        logger.info('delete_old_rows')
        if len(self._collected_data) > 0:
            _whole_table1 = sheet1.get_all_values()
            check_list = [l[url] for l in _whole_table1][1:][::-1]
            # logger.debug('check_list is ' + str(check_list))
            # logger.debug('legal is ' + str(legal))

            body = self._get_delete_dimensions_body(check_list, _whole_table1)

            logger.debug(body)
            if body['requests']:
                sh.batch_update(body)

    def _get_delete_dimensions_body(self, check_list, _whole_table1):
        """Итерирование списков для удаления записей в таблице

        Формирует тело запроса для удаления строк одним запросом
        """
        check_list_len = len(check_list) + 1
        body = {
            'requests': []
        }
        last_row_i = -10
        for url_i_, url_ in enumerate(check_list):
            row_i = check_list_len - url_i_ - 1
            if 'parser' in _whole_table1[row_i] and url_ not in self._collected_data:
                delete_row = f'Удалена строка {row_i + 1} {url_}'
                logger.debug(delete_row)
                if abs(row_i - last_row_i) == 1:
                    body['requests'][-1]['deleteDimension']['range']['startIndex'] -= 1
                else:
                    delete_dimension = {
                        'deleteDimension': {
                            'range': {
                                'sheetId': sheet1.id,
                                'dimension': 'ROWS',
                                'startIndex': row_i,
                                'endIndex': row_i + 1,
                            }
                        }
                    }
                    body['requests'].append(delete_dimension)
                last_row_i = row_i
        return body
