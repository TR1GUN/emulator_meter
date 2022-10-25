# Здесь расположим имитатор ответов счетчика
import random
import struct
from datetime import date, datetime, timedelta
import xml.etree.ElementTree as xmltree
import time
import os
from xml.dom import minidom
import json
from DataBase_SimulatorMeter import Meter_DataBase

# # Для начала пропишем наш файл со значениями
# path = '/'.join((os.path.abspath(__file__).replace('\\', '/')).split('/')[:-1])
times = 1

# # Получаем файл с параметрами
# valuesbank = xmltree.parse(path + '/values.xml').getroot()
# path_db = path

#
# def parse_values():
#     """Итак у нас есть функция чтения значений - Это важно"""
#     # Сначала читаем наш JSON
#     try:
#         jsonfile = open(path + '/values.json')
#         json_text = jsonfile.read()
#         valuesbank = json.loads(json_text)
#     except:
#         valuesbank = xmltree.parse(path + '/values.xml').getroot()
#
#     return valuesbank


# Набор скоростей
def switch_energ_baudrates(case):
    return {
        b'0': 300,
        b'1': 600,
        b'2': 1200,
        b'3': 2400,
        b'4': 4800,
        b'5': 9600,
    }.get(case, None)


# РАсчет ВСС
def calcbcc(rx):
    lrc = 0
    for x in rx:
        lrc += x
    lrc &= 0x7f
    lrc = hex(lrc)
    lrc = int(lrc, 16)
    return struct.pack('B', lrc)


# Класс имитатор
class SimulatorMeterEnergomera:
    """
    Эмулятор Счетчика ЭНЕРГОМЕРА 303\301

    В этом классе описана вся логика счетчика

    Используется:

    Транспортный уровень -
        Поля которые нужны для составления пакетов по протоколу ГОСТ МЭК 61107-2001
        Подробнее - 5.3 Форматы сообщений(с.9), Режим передачи - Тип С - (с.16)

    Нагрузочный уровень -
        Протокол Энергомеры СЕ - 303\301
    """
    # ----- МЭК -----
    # Начало заголовка
    _soh = b'\x01'
    # Символ начала блока нагрузочных байтов
    _stx = b'\x02'
    # Символ конца блока нагрузочных байтов
    _etx = b'\x03'
    # Символ подтверждения
    _ack = b'\x06'
    # Символ повторного запроса
    _nak = b'\x15'
    # Символ завершения - Сообщение
    _cr = b'\r'
    # Символ завершения - Строка
    _lf = b'\n'
    # Набор данных
    _data = b'\x06\x06\x06'

    _dataargs = b''

    _readen_args = b''

    _lbrace = b''

    _rbrace = b''

    _c = b''
    # Завершение обмена - Команда конца передачи
    _close = b'\x01B0\x03u'

    # ------ Поля необходимые для формирования ответа ------
    # Тип полученной команды
    _type = None
    # Генерируемый ответ
    _answer = b''
    # Запрос
    _response = bytearray()

    # Ответ на вопрос
    _response_answer = None

    # -----
    # Команда запроса
    _request = b''

    # Список типов ответов во время сессии обмена

    _answerbank = \
        {
            # Приветствие
            'hello': None,
            # Запрос конфигурации
            'confirm': None,
            # Авторизация
            'auth': bytes(_ack),
            # Выполнение команд
            'CMD': b'',
            # Для плохого запроса
            'None': b''
        }

    # Список ассоциаций тегов - Запрос типов данных - UPD : Представлено ниже
    # args = {}
    # Список ассоциаций тегов измерений различных запросов типов данных
    _tags = \
        {
            b'FREQU': 'Freq',
            b'POWPP': 'P',  #
            b'POWEP': 'PS',
            b'POWPQ': 'Q',  # QC , QA , QB
            b'POWEQ': 'QS',  # QS
            # b'COS_f': 'CF',
            b'COS_f': 'kP',
            b'VOLTA': 'U',
            b'CURRE': 'I',
            b'CORUU': 'Ang',
            b'ET0PE': 'A+',
            b'ET0PI': 'A-',
            b'ET0QE': 'R+',
            b'ET0QI': 'R-',
            b'ENDPE': 'dA+',
            b'ENDPI': 'dA-',
            b'ENMPE': 'MA+',
            b'ENMPI': 'MA-',
            b'EADPE': 'dCA+',
            b'EADPI': 'dCA-',
            b'EADQE': 'dCR+',
            b'EADQI': 'dCR-',
            b'EAMPE': 'MCA+',
            b'EAMPI': 'MCA-',
            b'EAMQE': 'MCR+',
            b'EAMQI': 'MCR-',
            b'ENDQE': 'dR+',
            b'ENDQI': 'dR-',
            b'ENMQE': 'MR+',
            b'ENMQI': 'MR-',
            b'GRAPE': 'DPP+',
            b'GRAPI': 'DPP-',
            b'GRAQE': 'DPQ+',
            b'GRAQI': 'DPQ-',
            # UPD : ЖУрналы
            # ВЫХОД ЗА ПРЕДЕЛЫ ФАЗОВОГО ЗНАЧЕНИЯ
            b'JOVER': 'Journal',
            # ФАЗа вкл/выкл
            b'PHASE': 'Journal',
            # Корекция часов
            b'JCORT': 'Journal',
            # вскрытие счетчика
            b'DENIA': 'Journal',
            # Электронная пломба - плока выдает ошибку
            b'ELOCK': 'Journal',
            # Журанл программирования
            b'ACCES': 'Journal'
        }

    # -------------------- Данные счетчика --------------------
    # Основная конфигурация счетчика - Данные измерения постоянные
    Config = \
        {
            # Имя счетчика
            'name': "CE303",
            # Адрес
            'address': "141227285",
            # Пароль
            'password': "777777",
            # Серийный номер
            'snumber': "009218054000006",
            # Изготовитель
            'maker': "energomera",
            # Версия ревизии
            'version': "v11",
            # Внутреннее обозначение модели
            'model_code': "226",
            # Наличие генерации случайным образом
            'random': "0",
            # Проверка даты
            'datecheckmode': "0",
            # Временой промежуток между ответами
            'respondtimeout': "500",

            # ---
            "const": 1.0,
            # "kI": 0.99,
            # "kU": 0.99,
            "isAm": True,
            "isClock": True,
            "isCons": True,
            "isDst": False,
            "isRm": True,
            "isRp": True,
            "isTrf": True,
            "cTime": 30,
            "DayConsDepth": 44,
            "DayDepth": 44,
            "MonConsDepth": 13,
            "MonDepth": 12,
            "VarConsDepth": 0,
            "serial": "009218054000006",
            "dDay": 44,
            "cArrays": 1,
            "model": "CE303",
        }

    # Серийник
    _serial = None
    # Модель счетчика
    _model = ''

    # Значения данных измерений счетчиков
    valuesbank = \
        {

        }

    def __init__(self, Meter_config: [dict] = None, Meter_values: [dict] = None):
        """
        Делаем конструктор Имитатора счетчика
        :param Meter_config: Настройки конфигурации счетчика
        :param Meter_values: Данные счетчика
        """

        # Определяем наш словарь который содержит значения данных
        self.valuesbank = \
            {
                "const": 1.0,
                # "kI": 0.99,
                # "kU": 0.99,
                "isAm": True,
                "isClock": True,
                "isCons": True,
                "isDst": False,
                "isRm": True,
                "isRp": True,
                "isTrf": True,
                "cTime": 30,
                "DayConsDepth": 44,
                "DayDepth": 44,
                "MonConsDepth": 13,
                "MonDepth": 12,
                "VarConsDepth": 0,
                "serial": "009218054000006",
                "dDay": 44,
                "cArrays": 1,
                "model": "CE303",

                # БУФЕР
                'Journal': ['ERROR - buffer empty'],

                # Показания Энергии
                'ElectricEnergyValues': {},
                # Показания Сети
                'ElectricQualityValues': {},
                # Профиль Мощности
                'ElectricPowerValues': {},

            }

        # Модель - перезаполняем поле
        self.model = str(self.Config.get("model_code"))
        # Служебные настройки - хз для чего
        self.times = 1
        self.datecheck = int(self.Config.get("datecheckmode"))
        self.respondtimeout = int(self.Config.get("respondtimeout")) * 0.001
        self.datecheckcount = 1

        # ------------------------------------
        # Теперь загружаем внутрение показатели счетчика -
        # Сначала Получаем дату
        self.time_now = datetime.now()

        # Переопределяем переменные основных команд
        self._start = b''
        self._address = b''
        self._exclam = b''
        self._bcc = b''
        self._c = b''
        self._d = b''
        self._v = b''
        self._z = b''
        self._y = b''
        self._eot = b''
        # Инициализируем наш адрес
        self._counter_address = self.Config.get("address").encode()

        # ТЕПЕРЬ ГОТОВЫ К РАБОТЕ :
        # self._response = request
        # # Запускаем -
        # self.response_answer = self.__parse_request()
        # после того как дали ответ - записываем дату ответа
        self.record_timenow()

    # -------------------------------ОСНОВНАЯ КОМАНДА РАБОТЫ С ВИРТУАЛЬНЫМ СЧЕТЧИКОМ------------------------------------
    def command(self, command):
        """
        Основной метод работы со счетчиком.
        Отправляем команду - Получаем на нее ответ.

        :param command: - байтовая строка - Сюда пихаем команду на которую надо получить ответ

        :return: И получаем наш ответ
        """
        # Получаем команду
        self._request = command

        # self._response = command
        # Запускаем -
        self.response_answer = self.__parse_request()
        # после того как дали ответ - записываем дату ответа
        # self.record_timenow()

        return self.response_answer

    # ---------------------------------------------УСТАНОВКА СЕРИЙНИКА------------------------------------------------
    def Set_Serial(self, serial):
        """
        Этот метод используется , для того чтоб задать серийный номер счетчика
        :param serial:
        :return:
        """
        self.serial = serial

    # ---------------------------------------------УСТАНОВКА СЕРИЙНИКА------------------------------------------------
    def Set_Data(self, data):
        """
        Этот метод используется для того чтоб задать данные в формате JSON что записываем
        :param data:
        :return:
        """
        vals = data.get('vals')

        # Проверяем валидацию json
        try:
            element = vals[0]["tags"][0]["tag"]

            # ТЕПЕРЬ НАДО ПОНЯТЬ МЫ ПОЛУЧИЛИ ЖУРНАЛЫ ИЛИ НЕТ
            if element in ['event', 'eventId', 'journalId']:
                # если получили журналы , то записываем их в буффер журналов
                self.__adding_journal_values(vals)
            # иначе - опускаем в перезапись по таймштапам
            else:
                self.__adding_values_from_json(vals)
        except:
            print('***ERROR : ВАЛИДАЦИЯ JSON НЕУСПЕШНА***')

    # -------------------------------СЛУЖЕБНЫЕ КОМАНДЫ РАБОТЫ С ВИРТУАЛЬНЫМ СЧЕТЧИКОМ----------------------------------
    #
    # # Функция загрузки параметров из values.xml
    # def __load_parametrs_from_xml(self):
    #     """
    #     В Этом методе загружаем параметры в наш valuesbank из xml - Даныный метод - обязательный
    #
    #     :return:
    #     """
    #     # Парсим файл
    #     valuesbank = xmltree.parse(path + '/values.xml').getroot()
    #     # Берем словарь
    #     valuesbank_dict = {}
    #     # Загружаем сначала таймштамп -
    #     # Он идет обычным словарем
    #     valuesbank_dict.update(valuesbank.attrib)
    #     # Теперь проходимся по каждому элементу
    #     for child in valuesbank:
    #         valuesbank_dict[child.attrib['code']] = child.text
    #
    #     # Теперь изменяем таймштамп на текущий системный
    #     valuesbank_dict['time'] = self.time_now
    #     # СОХРАНЯЕМ ЭТО ПО КЛЮЧУ - Now
    #     self.valuesbank['NOW'] = valuesbank_dict

    # # Функция Парсинга джейсон и заполнение данных поверх нашей xml
    # def __parse_JSON(self):
    #     """
    #     Функция Парсинга джейсон и заполнение данных поверх нашей xml
    #
    #     :return:
    #     """
    #     try:
    #         jsonfile = open(path + '/values.json')
    #         json_text = jsonfile.read()
    #         import json
    #         primary_valuesbank = json.loads(json_text)
    #     except:
    #         print('Не удалось прочитать JSON, используются значения по умолчанию')
    #         primary_valuesbank = None
    #
    #     # Если он не пустой , то переформатируем до нужного вида
    #     if primary_valuesbank is not None:
    #         vals = primary_valuesbank.get('vals')
    #
    #         # Проверяем валидацию json
    #         try:
    #             element = vals[0]["tags"][0]["tag"]
    #
    #             # ТЕПЕРЬ НАДО ПОНЯТЬ МЫ ПОЛУЧИЛИ ЖУРНАЛЫ ИЛИ НЕТ
    #             if element in ['event', 'eventId', 'journalId']:
    #                 # если получили журналы , то записываем их в буффер журналов
    #                 self.__adding_journal_values(vals)
    #             # иначе - опускаем в перезапись по таймштапам
    #             else:
    #                 self.__adding_values_from_json(vals)
    #         except:
    #             print('***ERROR : ВАЛИДАЦИЯ JSON НЕУСПЕШНА***')
    #
    #     # else:
    #     #     self.values_dict_with_timestamp = {datetime.now(): None}

    def __adding_values_from_json(self, vals):
        """
        Добавление значений из JSON  в наш банк значений

        :return:
        """
        # дЕЛАЕМ СЛОВАРЬ
        valuesbank_dict = {}
        # Начинаем перебирать наш словарь
        for i in range(len(vals)):
            tags_dict = {}
            # Если нет
            # ЗАПОЛНЯЕМ НАШ СЛОВАРЬ ЗНАЧЕНИЯМИ
            for x in range(len(vals[i]["tags"])):
                tag = vals[i]["tags"][x]["tag"]
                val = vals[i]["tags"][x]["val"]
                tags_dict[tag] = val
            # ПОСЛЕ ЧЕГО ПЕРЕВОДИМ ЭТОТ СЛОВАРЬ ЗНАЧЕНИЙ ДОСТУПНЫМ ПО UNIX TIME в качестве ключа
            # а не - лучше использовать юникс тайм
            unix_time = vals[i]["time"]
            valuesbank_dict[unix_time] = tags_dict
            # ------------------------------------------------>
            # Если нам попался профиль мощности - добавляем в него
            if vals[i].get('type') in 'ElArr1ConsPower':
                self.valuesbank['ElectricPowerValues'][unix_time] = tags_dict
        # ------------------------------------------------>
        # СТАВИМ ПОСЛЕДНЫЙ ТАЙМШТАМП В КАЧЕСТВЕ ЗНАЧЕНЯИ ПО УМОЛЧАНИЮ
        self.valuesbank['time'] = unix_time
        # ПОСЛЕДНИЙ ТАЙМШТАМП обновляем ключ NOW или с таймштампом 0
        # ЕСли таймштамп со значением 0 есть - то его загружаем в текущие
        if valuesbank_dict.get(0) is not None:
            self.valuesbank['NOW'].update(valuesbank_dict[0])
        # Если нет - То ставим в текущие послений таймштамп
        else:
            self.valuesbank['NOW'].update(valuesbank_dict[unix_time])
        # остальные таймштампы записываем в основной словарь
        self.valuesbank.update(valuesbank_dict)

    def __adding_journal_values(self, json_values):
        """
        Данный метод нужен для нормального парсинга значений журналов - и добавления их в буффер в правильном виде
        :param values_dict:
        :return:
        """

        # Сделаем словарь для определеняи позиции байта
        # в нем - журнал айди отдает позицию бита

        # Журнал айди берется согласно протоколу

        byte_position = \
            {
                20: 3,
                21: 0,
                22: 4,
                23: 1,
                24: 5,
                25: 2,

                9: 0,
                10: 1,
                11: 2,
                1: 6,

                6: 3,
                3: 5,

            }
        # Создаем буффер определенной длины - а именно количеству таймштампов в JSON
        journal_buffer = [None] * len(json_values)

        # Теперь - берем и правильно его заполняем
        for i in range(len(json_values)):
            # Сначала берем время

            timestamp = datetime.fromtimestamp(json_values[i]['time'])
            # Теперь делаем из него запис
            timestamp = str(timestamp.day) + '-' + str(timestamp.month) + '-' + str(timestamp.year)[-2:] + '-' + \
                        str(timestamp.hour) + '-' + str(timestamp.minute) + '-'

            # Теперь что делаем - Проходимся по значениям журнала
            tags_dict = {}
            for x in range(len(json_values[i]["tags"])):
                # Теперь что нам надо - вывезти все значения
                tag = json_values[i]["tags"][x]["tag"]
                val = json_values[i]["tags"][x]["val"]
                tags_dict[tag] = val
            # Теперь можно делать с ними разные манипуляции

            # Буффер - Выход за пределы минимального\максимального значения напряжения фазы
            if tags_dict['journalId'] in [20, 21, 22, 23, 24, 25]:
                # Берем позицию байта
                position = byte_position[tags_dict['journalId']]
                # упаковываем наш байт
                value_bytes = ''
                for byte in range(6):
                    # Если натыкаемся на позицию что нам нужна -
                    if byte in [position]:
                        value_bytes = value_bytes + str(tags_dict['event'])
                    # Иначе - Оставляем пустым
                    else:
                        value_bytes = value_bytes + '0'
                # Переворачиваем нашу строку
                value_bytes = value_bytes[::-1]
                # Переводим в десятичный инт
                value_bytes = int(value_bytes, 2)
                # И после чего добавляем к нашей строке записи
                journal_record = timestamp + str(value_bytes)
                # После чего добавляем ее по индексу в массив

            # Буффер - Включение/выключение фазы , включение выключения счетчика
            elif tags_dict['journalId'] in [1, 9, 10, 11]:

                # Берем позицию байта
                position = byte_position[tags_dict['journalId']]
                # упаковываем наш байт
                value_bytes = ''
                for byte in range(8):
                    # Если натыкаемся на позицию, что нам нужна -
                    if byte in [position]:
                        value_bytes = value_bytes + str(tags_dict['event'])
                    # Иначе - Оставляем пустым
                    else:
                        value_bytes = value_bytes + '0'
                # Переворачиваем нашу строку
                value_bytes = value_bytes[::-1]
                # Переводим в десятичный инт
                value_bytes = int(value_bytes, 2)
                # И после чего добавляем к нашей строке записи
                journal_record = timestamp + str(value_bytes)
                # После чего добавляем ее по индексу в массив

            # Буффер - Корекция времени
            elif tags_dict['journalId'] in [2]:
                # Берем значение времени - изменяем
                timestamp = timestamp.replace('-', '/')
                # Добавляем к нему цифру на которую изменили
                # value_bytes = tags_dict['event']
                value_bytes = 1
                journal_record = timestamp + str(value_bytes)
                # После чего добавляем ее по индексу в массив
            # Буффер - Несанкционированный доступ (вскрытие/закрытие заводской крышки)
            elif tags_dict['journalId'] in [8]:
                # Здесь все просто - добавляем время
                journal_record = timestamp[:-1]

            # Журнал тарифов
            elif tags_dict['journalId'] in [6]:
                journal_record = timestamp + '8'

            # Журнал Сброса накопленных параметров
            elif tags_dict['journalId'] in [3]:
                journal_record = timestamp + '32'

            # ИНАЧЕ - ЗАПОЛНЯЕМ НАШ БуФЕР ошибкой
            else:
                journal_record = 'ERR12'

            # после чего заполянем буффер
            journal_buffer[tags_dict['eventId']] = journal_record
        Journal = {'Journal': journal_buffer}
        self.valuesbank.update(Journal)

    # --------------------------------------------------------------------------------------------------------------
    # ------------------------------ ОСНОВНАЯ ЛОГИКА РАБОТЫ ВИРТУАЛЬНОГО СЧЕТЧИКА ----------------------------------
    # --------------------------------------------------------------------------------------------------------------
    # разобрать запрос и сгенерировать ответ
    def __parse_request(self):
        """
        Метод для чтения запроса и отдачи ответа

        :return: Ответ - байтовая строка
        """

        # Берем нашу команду, что получили
        request = self._request

        # Делаем начало ответа
        try:

            self.start = struct.pack('b', self._request[0])

        except Exception as e:
            print('ERROR -' + str(e), self._request[0])

            self.start = struct.pack('b', 1)

        try:
            self._parse_comand(command=self.start)

        except:

            # Итак - если у нас лажанула команда - то отправляем команду НЕ ПОНЕЛ
            print('*************************НЕ ПРАВИЛЬНАЯ КОМАНДА*************************\n ',
                  '*************************** ПЕРЕЗАПРАШИВАЕМ ***************************')
            self.type = 'CMD'
            self.answerbank['CMD'] = self.nak

        # Делаем ответ:
        # Определяем тип команд
        response = self.__makeanswer(self.type)

        return response

    # Делаем ответ
    def __makeanswer(self, anstype):
        """
        МЕТОД ДЛЯ ТОГО ЧТОБ СДЕЛАТЬ ОТВЕТ НА ЗАПРОС

        :param anstype:
        :return:
        """
        # ПО ТИПУ ЗАПРОСА ОПРЕДЕЛЯЕМ ОТВЕТ ЧЕРЕЗ СЛОВАРЬ ОТВЕТОВ
        self._answer = self.answerbank[anstype]

        return self.answer

    # --------------------------------------------------------------------------------------------------------------
    # ------------------------------------------- Рабочие методы ---------------------------------------------------
    # --------------------------------------------------------------------------------------------------------------
    #     Служебный метод парсинга команды
    def _parse_comand(self, command):
        """
        ЗДЕСЬ - ОПРЕДЕЛЯЕМ ПО ЗАГОЛОВКУ ТИП КОМАНДЫ _ И СООТВЕТСВЕННО ПИХАЕМ В НУЖНЫЙ РАЗДЕЛ
        :param command:
        :return:
        """
        if b'/' in command:
            self.__reqhello()
        elif self._ack in command:
            self.__confirm()
        elif self._soh in command:
            self.__prog()
        else:
            self.__empty()

    # -------------------------------------------------------------------------------------------------
    # ----------------------------    Обработка Различных Типов Команд     ----------------------------
    # -------------------------------------------------------------------------------------------------
    # Тип ответа "плоха"
    def __empty(self):
        """
        Не корректная команда - Возвращаем перезапрос и соответственно связь обрывается - см протокол обмена

        :return:
        """
        self._type = 'None'

        # # Возвращаем - команду НЕ понял
        # answer = self._nak
        # return answer

    # тип ответа "ПРИВЕТ"
    def __reqhello(self):
        """
        Данный метод нужен для составления ответа на ПРИВЕТ и возникновения первичной связи

        :return:
        """

        # разбираем ответ на "Привет"
        if len(self._response) > 1 and struct.pack('b', self._response[1]) == b'?':
            # Стартовый символ
            self._start += struct.pack('b', self._response[1])

            # Определяем тип операции как приветствие
            self._type = 'hello'

            if struct.pack('b', self._response[4]) == '!'.encode():
                self._address = bytes(self._response[2:4])
                self._exclam = struct.pack('b', self._response[4])
            else:
                self._address = bytes(self._response[2:5])
                self._exclam = struct.pack('b', self._response[5])
            self._cr = struct.pack('b', 13)
            self._lf = struct.pack('b', 10)

            # Делаем ответ на "Привет"
            # Для этого нам надо:
            # Имя счетчика
            name = self.Config.get("name", "").encode()
            # его версия
            version = self.Config.get("version", "").encode()
            # self.answerbank['hello'] = bytes(b'/EKT5' + name + version + self.cr + self.lf)

            # Создаем ответ
            self._answer = bytes(b'/EKT5' + name + version + self._cr + self._lf)

    # данный метод нужен для обмена информаций после привет
    def __confirm(self):
        """
        Данный метод нужен для установления связи после первичного привет и обмена конфигурацией счетчика

        :return:
        """
        # Разбираем вопрос к режиму программирования
        self._type = 'confirm'

        # Читаем запрос:

        self._v = struct.pack('b', self._response[1])

        self._z = struct.pack('b', self._response[2])

        self._y = struct.pack('b', self._response[3])

        self._cr = struct.pack('b', self._response[len(self._response) - 2])

        self._lf = struct.pack('b', self._response[len(self._response) - 1])

        # self._cr = struct.pack('b', 13)
        #
        # self._lf = struct.pack('b', 10)

        # Делаем ответ на запрос программирования
        name = self.Config.get("name", "").encode()


        self._answerbank['confirm'] = \
            bytes(
                  self._soh + b'P0' + self._stx + b'(' + self._counter_address + b')' + self._etx +
                  calcbcc(b'P0' + self._stx + b'(' + self._counter_address + b')' + self._etx)
            )

    # создать ответ на запросы авторизации и данных
    def __prog(self):

        """
        Данный метод нужен для составления нормального ответа после того как перешли в режим программирования -
        Здесь используется Сценарий обмена тип С -

        Здесь описана вся логика обмена основными командами

        :return:
        """
        # Если у нас пришла не пустота
        if self._response[1] is not None:
            # Читаем запрос
            self._c = struct.pack('b', self._response[1])

            # Блок авторизации
            if self._c == b'P':
                # Запускаем авторизацию
                self.__auth()

            # Блок запроса данных - основные страдания проходят именно в этом блоке -
            # Здесь уже нельзя быть косипошей чтоб ничего не сломать
            elif self._c == b'R':
                # Запускаем выполнение команды энергомеры
                self.__meter_command()

            # Блок записи
            elif self._c == b'W':
                # Определяем тип операции как команда
                self._type = 'CMD'
                # self._answer = b''
                # Отправляем Ок
                self._answerbank['CMD'] = self._ack

            elif self._c == b'B':
                # Определяем тип операции как команда
                self._type = 'CMD'
                # индикатор типа команды - здесь он int
                self._d = struct.pack('b', self._response[2])
                # self.answer = b''
                self._answerbank['CMD'] = b''
            # self.etx = struct.pack('b', self._response[len(self._response) - 2])
            self._etx = struct.pack('b', 3)
            # Пытаемся запаковать это

            try:
                self._bcc = struct.pack('b', self._response[len(self._response) - 1])

            # Если не получилось сразу, то запаковываем это альтернативно- ЭТО ОЧЕНЬ ВАЖНЫЙ МОМЕНТ
            #                   UPD
            # !!!!!Дело в том что энергомера использует протокол передачи 7е1!!!!!!
            # Это означает что в одном БАЙТЕ 7 БИТ
            # НЕТ, НЕ ТЕХ БИТ ЧТО В БАГАЖНИКЕ
            # ДА, В ШКОЛЕ УЧИЛИ ЧТО ИХ 8 как в денди
            # НО ЭТО НЕ ДЕНДИ А ЭНЕРГОМЕРА
            except:
                pack = self._response[len(self._response) - 1]
                # ПРИНУДИТЕЛЬНО ЗАПОКОВЫВАЕМ
                bcc_byte = pack.to_bytes(8, byteorder='big', signed=True)

                # Альтернативные пути запоковывания
                # unpack_1 = pack // 100
                # unpack_2 = pack % 100
                # bcc1 = struct.pack('b', unpack_1)
                # bcc2 = struct.pack('b', unpack_2)
                # bcc  = bcc1 + bcc2
                self._bcc = bcc_byte

    def __auth(self):
        """
        Блок авторизации

        :return:
        """
        # Определяем тип операции как АВТОРИЗАЦИЯ
        self._type = 'auth'

        # Читаем пришедшие данные:
        # индикатор типа команды - здесь он int
        self._d = struct.pack('b', self._response[2])
        # Объявление начала операции
        self._stx = struct.pack('b', self._response[3])
        # Служебный байт ?
        self._lbrace = struct.pack('b', self._response[4])
        # Сам наш пароль от Счетчика
        self._data = self._response[5:len(self._response) - 3]

        # Проверяем пароль
        password = self.Config.get("password").encode()
        if self._data != password:

            print("Пароль не совпал, лол")
            # print(u'Пароль не совпал пароль счетчика{0} и пароль УМ{1}'.format(str(
            #     self._counter.password, self.data)))
            # f = open(self.log, 'a')
            # timestamp = '>' + str(datetime.now().strftime("%d.%m.%y %H:%M:%S")) + '>'
            # f.writelines(timestamp + '\n')
            # f.writelines(u'Пароль не совпал пароль счетчика{0} и пароль УМ{1}'.format(str(
            #     self._counter.password, self.data)) + '\n')
            # f.close
            # return
        # Делаем ответ
        self._rbrace = struct.pack('b', self._response[len(self._response) - 3])

    def __meter_command(self):
        """
        Блок команд прибора учета

        :return:
        """
        # Определяем тип операции как Команда счетчика
        self._type = 'CMD'
        # Сохраняем идентификатор - он нам еще понадобиться
        tmp = self._stx
        # Читаем пришедшие данные:
        # индикатор типа команды - здесь он int
        self._d = struct.pack('b', self._response[2])
        # Объявление начала операции
        self._stx = struct.pack('b', self._response[3])

        # Парсим всю команду в кодировке энергомеры - Нужна, чтоб вытащить время
        self._comand_energomera_protocol = self._response[4:-2]
        # Парсим просто команду, без скобок
        self._data = bytes(self._response[4:9])
        # получение данных в первый раз
        # Пытаемся по команде узнать что надо отвечать
        try:
            # Итак, опускаем в нашу функцию парсинга времени
            # Опускаем нашу команду в словарь со всеми командами которые учтены тут
            self.__definion_datetime()
            # ТЕПЕРЬ ИЩЕМ НУЖНУЮ КОМАНДУ ЧТОБ ВЫЛОВИТЬ НУЖНЫЕ ЗНАЧЕНИЯ
            self._dataargs = self._args.get(self._data, self.get_random_bytes)(self, 1)

        except Exception as e:
            print('ОШИБКА', e)
            # ставим данные - пустоту
            self._dataargs = b''
        # Читаем конец команды
        self._lbrace = struct.pack('b', self._response[9])
        # Читаем дополнительные аргументы
        self._readen_args = bytes(self._response[10:len(self._response) - 3])
        # Читаем закрывающий символ
        self._rbrace = struct.pack('b', self._response[len(self._response) - 3])

        # проверяем, нужно ли использовать дополнительные аргументы
        if len(self._readen_args) == 0:

            tmp += bytes(self._data + self._lbrace + self._dataargs + self._rbrace + self._cr + self._lf)
            t = 2
            # Создаем ответ
            self._answerbank['CMD'] = tmp + self._etx + calcbcc(tmp[1:] + self._etx)
            # получение дополнительных данных, если запрос требует нескольких данных
            while t <= times:
                try:
                    self._dataargs = self._args.get(self._data, self.get_random_bytes)(self, t)
                except Exception as e:
                    print('ОШИБКА', e)
                tmp += bytes(self._data + self._lbrace + self._dataargs + self._rbrace + self._cr + self._lf)
                self._answerbank['CMD'] = tmp + self._etx + calcbcc(tmp[1:] + self._etx)
                t += 1

        # Если Команды нет, то отвечаем пустотой - нужно для архивных записей
        elif self._dataargs == b'':
            self._answerbank['CMD'] = self._stx + self._etx + self._dataargs + self._etx

        else:
            t = 2
            tmp += bytes(
                self._data + self._lbrace + self._dataargs + self._rbrace + self._cr + self._lf)
            self._answerbank['CMD'] = tmp + self._etx + calcbcc(tmp[1:] + self._etx)
            # получение дополнительных данных, если запрос требует нескольких данных
            while t <= times:
                try:
                    self._dataargs = self._args.get(self._data, self.get_random_bytes)(self, t)
                except Exception as e:
                    print('ОШИБКА', e)
                tmp += bytes(
                    self._data + self._lbrace + self._dataargs + self._rbrace + self._cr + self._lf)
                self._answerbank['CMD'] = tmp + self._etx + calcbcc(tmp[1:] + self._etx)
                t += 1

    # -----------------------Служебные методы для перезаписи Значений Относительно времени-----------------------------
    # ДАнная функция нужна чтоб определить тип даты-времени в запросе
    def __definion_datetime(self):
        """
        Данная команда нужна, чтоб найти необходимое время - Это важно, если читаем по глубине времени!!!

        :return:
        """

        type_datetime = \
            {
                # Срез по дням
                b'ENDPE': 'd',
                b'ENDPI': 'd',
                b'ENDQE': 'd',
                b'ENDQI': 'd',
                # Срез по месяцам
                b'ENMPE': 'M',
                b'ENMPI': 'M',
                b'ENMQE': 'M',
                b'ENMQI': 'M',
                # Срез по дням потребление
                b'EADPE': 'dC',
                b'EADPI': 'dC',
                b'EADQE': 'dC',
                b'EADQI': 'dC',
                # Срез по месяцам потребление
                b'EAMPE': 'MC',
                b'EAMPI': 'MC',
                b'EAMQE': 'MC',
                b'EAMQI': 'MC',
                # профили мощности первого архива электросчетчика - те что каждые пол часа
                b'GRAPE': 'DP',
                b'GRAPI': 'DP',
                b'GRAQE': 'DP',
                b'GRAQI': 'DP',

                # МГНОВЕННЫЕ ПОКАЗАНИЯ !!!
            }
        # Ищем нашу команду в списке выше
        data = bytes(self._data)
        type_date = type_datetime.get(data)

        if type_date is not None:
            # Далее опускаем в функцию перезаписи нашего попаденца
            self.__rewrited_value_dict(type_date)

    # Метод для перезаписи нашего банка значений для нужного времени!!!
    def __rewrited_value_dict(self, type_date):
        """
        Метод перезаписывает изначальные значения в зависимости от таймштампа
        :param type_date: тип даты
        :return:
        """
        # Здесь нам понадобятся регульрные выражения чтоб не колхозить
        import re
        energomera_command_protocol = self._comand_energomera_protocol
        # Теперь парсим дату - Она в скобках
        if type_date == 'd':
            # итак - Работаем Только с днем
            request_date = re.findall(r'\d{2}\.\d{1,2}\.\d{2}', str(energomera_command_protocol.decode()))
            # Теперь после того как вытащили дату ее можно употребить В ФОРМАТЕ ДД , ММ, ГГ
            request_date = request_date[0].split('.')
            # Собираем нашу дату
            # find_date = int(time.mktime(find_date.timetuple()))
            find_date = self.__consrtuct_date_by_find(year=int('20' + str(request_date[2])),
                                                      month=int(request_date[1]),
                                                      day=int(request_date[0])
                                                      )
            # И поскольку это энергомера - прибавляем один день
            energomera_delta = timedelta(days=1)
            # переводим из юникс тайм в нормальный вид, и прибомвляем день
            energomera_time = datetime.fromtimestamp(find_date) + energomera_delta
            # после чего обратно запаковываем в юнекс тайм
            find_date = time.mktime(energomera_time.timetuple())

        elif type_date == 'M':
            # итак - Работаем c месяцем
            request_date = re.findall(r'\d{1,2}\.\d{2}', str(energomera_command_protocol.decode()))
            # Теперь после того как вытащили дату ее можно употребить В ФОРМАТЕ ММ, ГГ
            request_date = request_date[0].split('.')
            # Собираем нашу дату
            month = int(request_date[0]) + 1
            year = int('20' + str(request_date[1]))
            # А теперь фокус - если у нас получилось перебор , переводим часы

            if month > 12:
                month = 1
                year = year + 1

            find_date = self.__consrtuct_date_by_find(
                year=year,
                month=month,
                day=1
            )

        elif type_date == 'dC':
            # итак - Работаем Только с днем
            request_date = re.findall(r'\d{2}\.\d{1,2}\.\d{2}', str(energomera_command_protocol.decode()))
            # Теперь после того как вытащили дату ее можно употребить В ФОРМАТЕ ДД , ММ, ГГ
            request_date = request_date[0].split('.')
            # Собираем нашу датy
            # Теперь переводим это все в Unixtime
            # find_date = int(time.mktime(find_date.timetuple()))
            find_date = self.__consrtuct_date_by_find(year=int('20' + str(request_date[2])),
                                                      month=int(request_date[1]),
                                                      day=int(request_date[0])
                                                      )

        elif type_date == 'MC':
            # итак - Работаем c месяцем
            request_date = re.findall(r'\d{1,2}\.\d{2}', str(energomera_command_protocol.decode()))
            # Теперь после того как вытащили дату ее можно употребить В ФОРМАТЕ ММ, ГГ
            request_date = request_date[0].split('.')
            # Собираем нашу дату
            month = int(request_date[0])
            year = int('20' + str(request_date[1]))
            # А теперь фокус - если у нас получилось перебор , переводим часы

            if month > 12:
                month = 1
                year = year + 1

            find_date = self.__consrtuct_date_by_find(
                year=year,
                month=month,
                day=1
            )

        elif type_date == 'DP':
            # итак - Работаем с получасом
            request_date = re.findall(r'\d{1,2}\.\d{1,2}\.\d{2}.\d{1,2}', str(energomera_command_protocol.decode()))
            # Теперь после того как вытащили дату ее можно употребить В ФОРМАТЕ ДД , ММ, ГГ, номер получаса
            request_date = request_date[0].split('.')
            # Собираем нашу датy
            # Теперь переводим это все в Unixtime
            # Итак - Ищем день
            find_date = self.__consrtuct_date_by_find(year=int('20' + str(request_date[2])),
                                                      month=int(request_date[1]),
                                                      day=int(request_date[0])
                                                      )

            # И поскольку это энергомера - прибавляем один день
            # energomera_delta = timedelta(days=1)
            # переводим из юникс тайм в нормальный вид , и прибомвляем день
            # energomera_time = datetime.fromtimestamp(find_date) + energomera_delta
            # после чего обратно запаковываем в юнекс тайм
            # find_date = time.mktime(energomera_time.timetuple())
            # Теперь к этому дню надо добавить нужное колличество минут
            timesDP = timedelta(minutes=30 * int(request_date[3]))

            # Переводим это в юнекс тайм и плюсуем
            find_date = datetime.fromtimestamp(find_date)
            find_date = find_date + timesDP
            # И переводим обрвтно в юникс тайм
            find_date = int(time.mktime(find_date.timetuple()))

        else:
            # НЕ УДАЛОСЬ ПРЕОБРАЗОВАТЬ ДАТУ
            find_date = int(time.mktime(datetime.now().timetuple()))
        try:
            # А после ищем значения по этой дате
            # --
            # values_dict = self.values_dict_with_timestamp[find_date]
            # --

            values_dict = self.valuesbank.get(find_date)
            # --
            if values_dict is not None:
                # Теперь что делаем - Одновляем наш список до нужных значений !!!
                correct_values_dict = {}
                for key in list(values_dict.keys()):
                    correct_values_dict[type_date + str(key)] = values_dict[key]

                # После чего обновляем наш список
                self.valuesbank['NOW'].update(correct_values_dict)
            # Итак - если у нас пустые значения - То обнуляем все значения - Для получения пустых значений
            else:

                # Если не находим нужный таймштамп - ставим пометку, что измерения не проводились
                no_measurements_were_taken_dict = \
                    {
                        # Срез по дням
                        'd':
                            {
                                'dA+0': None,
                                'dA+1': None,
                                'dA+2': None,
                                'dA+3': None,
                                'dA+4': None,
                                'dA+5': None,
                                'dA-0': None,
                                'dA-1': None,
                                'dA-2': None,
                                'dA-3': None,
                                'dA-4': None,
                                'dA-5': None,
                                'dR+0': None,
                                'dR+1': None,
                                'dR+2': None,
                                'dR+3': None,
                                'dR+4': None,
                                'dR+5': None,
                                'dR-0': None,
                                'dR-1': None,
                                'dR-2': None,
                                'dR-3': None,
                                'dR-4': None,
                                'dR-5': None
                            },
                        # Срез по месяцам
                        'M':
                            {

                                'MA+0': None,
                                'MA+1': None,
                                'MA+2': None,
                                'MA+3': None,
                                'MA+4': None,
                                'MA+5': None,
                                'MA-0': None,
                                'MA-1': None,
                                'MA-2': None,
                                'MA-3': None,
                                'MA-4': None,
                                'MA-5': None,
                                'MR+0': None,
                                'MR+1': None,
                                'MR+2': None,
                                'MR+3': None,
                                'MR+4': None,
                                'MR+5': None,
                                'MR-0': None,
                                'MR-1': None,
                                'MR-2': None,
                                'MR-3': None,
                                'MR-4': None,
                                'MR-5': None
                            },
                        # Срез по дням потребление
                        'dC':
                            {
                                'dCA+0': None,
                                'dCA+1': None,
                                'dCA+2': None,
                                'dCA+3': None,
                                'dCA+4': None,
                                'dCA+5': None,
                                'dCA-0': None,
                                'dCA-1': None,
                                'dCA-2': None,
                                'dCA-3': None,
                                'dCA-4': None,
                                'dCA-5': None,
                                'dCR+0': None,
                                'dCR+1': None,
                                'dCR+2': None,
                                'dCR+3': None,
                                'dCR+4': None,
                                'dCR+5': None,
                                'dCR-0': None,
                                'dCR-1': None,
                                'dCR-2': None,
                                'dCR-3': None,
                                'dCR-4': None,
                                'dCR-5': None,
                            },
                        # Срез по месяцам потребление
                        'MC':
                            {
                                'MCA+0': None,
                                'MCA+1': None,
                                'MCA+2': None,
                                'MCA+3': None,
                                'MCA+4': None,
                                'MCA+5': None,
                                'MCA-0': None,
                                'MCA-1': None,
                                'MCA-2': None,
                                'MCA-3': None,
                                'MCA-4': None,
                                'MCA-5': None,
                                'MCR+0': None,
                                'MCR+1': None,
                                'MCR+2': None,
                                'MCR+3': None,
                                'MCR+4': None,
                                'MCR+5': None,
                                'MCR-0': None,
                                'MCR-1': None,
                                'MCR-2': None,
                                'MCR-3': None,
                                'MCR-4': None,
                                'MCR-5': None,
                            },
                        # профили мощности первого архива электросчетчика - те что каждые пол часа
                        'DP':
                            {
                                'DPP+': None,
                                'DPP-': None,
                                'DPQ+': None,
                                'DPQ-': None
                            },
                    }
                # Теперь - Получаем наши значения
                correct_values_dict = no_measurements_were_taken_dict[type_date]
                # После чего обновляем наш список
                self.valuesbank['NOW'].update(correct_values_dict)

        except KeyError:
            print('   ***ERROR НЕ УДАЛОСЬ НАЙТИ ВРЕМЯ ***\n', find_date)
            pass

    def __consrtuct_date_by_find(self, year: int = 0, month: int = 0, day: int = 0, hour: int = 0, minute: int = 0):

        """
        Итак - очень важная хрень - конструктор нужной даты для последующего ее поиска- Это важно!!
        :return:
        """
        # ИТАК - ЕСЛИ ГОД , МЕСЯЦ , ЧИСЛО ИЛИ ЧТО ТО ИЗ ЭТОГО НЕ ЗАДАВАЛОСЬ ПО КАКОЙ ТО ПРИЧИНЕ - ПЕРЕОПРЕДЕЛЯЕМ НА
        # ТЕКУЩЕЕ
        if year == 0:
            year = self.time_now.year

        if month == 0:
            month = self.time_now.month

        if day == 0:
            day = self.time_now.day

        find_date = datetime.now()
        find_date = datetime.replace(find_date,
                                     year=year,
                                     month=month,
                                     day=day,
                                     hour=hour,
                                     minute=minute,
                                     second=0,
                                     microsecond=0
                                     )
        # Теперь переводим это все в Unixtime
        find_date = int(time.mktime(find_date.timetuple()))

        # А ТЕПЕРЬ ВОЗВРАЩАЕМ В ЗАД
        return find_date

    # -----------------------------------------------------------------------------------------------------------------
    # --------------------------------- МЕТОДЫ ДЛЯ ПОИСКА НУЖНЫХ ДАННЫХ -----------------------------------------------
    # -----------------------------------------------------------------------------------------------------------------
    #  Показатели энергии на конец дня, месяц, и моментные показатели
    def __get_bytes_for_energy_and_set_times_by_El_Energy(self, t):
        """
        Здесь считываем значения для ElMomentEnergy , ElDayEnergy , ElMonthEnergy

        МОМЕНТНЫЕ показатели энергии

        :param t:
        :return:
            """
        global times
        times = 6
        # Генерируем рандомно все это
        if self.Config.get(random) == '1':
            var = "%.3f" % (1000 * random.random())

        # Если не стоит рандомно, то делаем это все по шаблону
        else:
            # Берем тэг что нам нужен
            tag = str(self._tags.get(self._data)) + str(t - 1)
            # Теперь по значению этого тэга ищем значение в нашем словаре

            # ++ Заглушка - если значения нет в наших значениях
            var = self.valuesbank['NOW'].get(tag)
            # if var is not None:
            #
            #     var = float(var) / 1000
            #     # Теперь берем и округляем
            #     var = float('{:.6f}'.format(var))
            #     var = str(var)
            # else:
            #     var = ''

            if var is None:
                var = 0
            var = float(var) / 1000
            # Теперь берем и округляем
            var = float('{:.6f}'.format(var))
            var = str(var)

            # Если ломается - то идем по старому сценарию
        return var.encode()

    # Значения Напряжения
    def __get_bytes_for_Volts(self, t):

        global times
        times = 3
        if self.Config.get(random) == '1':
            var = "%.3f" % (float(219) + 10 * random.random())
        else:
            # ЕСли не стоит рандомно - то делаем это все по шаблону
            # Берем тэг что нам нужен

            tag_dict = {0: 'A', 1: 'B', 2: 'C'}
            tag = str(self._tags.get(self._data)) + str(tag_dict[t - 1])

            # Теперь по значению этого тэга ищем значение в нашем словаре
            var = float(self.valuesbank['NOW'][tag])
            var = str(var)
        return var.encode()

    # Значения Q
    def __get_bytes_for_Power(self, t):

        global times
        times = 3
        if self.Config.get(random) == '1':
            var = str("%.3f" % random.random())
        else:
            # ЕСли не стоит рандомно, то делаем это все по шаблону
            # Берем тэг что нам нужен
            tag = str(self._tags.get(self._data)) + str(t - 1)
            # Теперь по значению этого тэга ищем значение в нашем словаре
            var = self.valuesbank['NOW'][tag]
            var = float(var)
            var = str(var)
            # Если ломается - то идем по старому сценарию
        return var.encode()

    def __get_bytes_for_PowerPS(self, t):

        global times
        times = 3
        if self.Config.get(random) == '1':
            var = str("%.3f" % random.random())
        else:
            # ЕСли не стоит рандомно, то делаем это все по шаблону
            # Берем тэг что нам нужен
            tag = str(self._tags.get(self._data))
            # Теперь по значению этого тэга ищем значение в нашем словаре
            var = self.valuesbank['NOW'][tag]
            var = float(var) / 1000
            var = str(var)
            # Если ломается - то идем по старому сценарию
        return var.encode()

    def __get_bytes_for_PowerQS(self, t):

        global times
        times = 3
        if self.Config.get(random) == '1':
            var = str("%.3f" % random.random())
        else:
            # ЕСли не стоит рандомно, то делаем это все по шаблону
            # Берем тэг что нам нужен
            tag = str(self._tags.get(self._data))
            # Теперь по значению этого тэга ищем значение в нашем словаре
            var = self.valuesbank['NOW'][tag]
            var = float(var) / 1000
            var = str(var)
            # Если ломается - то идем по старому сценарию
        return var.encode()

    def __get_bytes_for_PowerABC(self, t):

        global times
        times = 3
        if self.Config.get(random) == '1':
            var = str("%.3f" % random.random())
        else:
            # ЕСли не стоит рандомно то делаем это все по шаблону
            # Берем тэг что нам нужен

            tag_dict = {0: 'A', 1: 'B', 2: 'C'}
            tag = str(self._tags.get(self._data)) + str(tag_dict[t - 1])
            # tag = str(self.tags.get(self.data)) + str(t - 1)
            # Теперь по значению этого тэга ищем значение в нашем словаре

            var = float(self.valuesbank['NOW'][tag]) / 1000
            var = str(var)
            # Если ломается - то идем по старому сценарию
        return var.encode()

    def __get_bytes_for_Power_PA_PB_PC(self, t):

        global times
        times = 3
        if self.Config.get(random) == '1':
            var = str("%.3f" % random.random())
        else:
            # ЕСли не стоит рандомно то делаем это все по шаблону
            # Берем тэг что нам нужен

            tag_dict = {0: 'A', 1: 'B', 2: 'C'}
            tag = str(self._tags.get(self._data)) + str(tag_dict[t - 1])
            # tag = str(self.tags.get(self.data)) + str(t - 1)
            # Теперь по значению этого тэга ищем значение в нашем словаре

            var = float(self.valuesbank['NOW'][tag]) / 1000
            var = str(var)
            # Если ломается - то идем по старому сценарию
        return var.encode()

    # Сила ТОКА
    def __get_bytes_Current(self, t):

        global times
        times = 3
        if self.Config.get(random) == '1':
            var = str("%.3f" % random.random())
        else:

            # Еcли не стоит рандомно то делаем это все по шаблону
            # Берем тэг что нам нужен

            tag_dict = {0: 'A', 1: 'B', 2: 'C'}
            tag = str(self._tags.get(self._data)) + str(tag_dict[t - 1])
            # Теперь по значению этого тэга ищем значение в нашем словаре

            var = float(self.valuesbank['NOW'][tag])
            var = str(var)
            # Если ломается - то идем по старому сценарию

        return var.encode()

        # УГОЛ

    def __get_bytes_for_Angles(self, t):  # angles

        global times
        times = 3
        if self.Config.get(random) == '1':
            var = "%.1f" % (100 * random.random())
        else:

            tag_dict = {0: 'AB', 1: 'BC', 2: 'AC'}
            # Берем тэг что нам нужен

            tag = str(self._tags.get(self._data)) + str(tag_dict[t - 1])
            # Теперь по значению этого тэга ищем значение в нашем словаре
            var = float(self.valuesbank['NOW'][tag])

            # ЗДЕСЬ ОЧЕНЬ ВАЖНО AngAC - Надо реверснуть
            if tag == 'AngAC':
                var = var * -1

            var = str(var)
            # Если ломается - то идем по старому сценарию

        return var.encode()

    # cosinus
    def __get_bytes_for_Cos(self, t):  # cosinus

        global times
        times = 4
        if self.Config.get(random) == '1':
            var = str("%.2f" % random.random())
        else:
            # Берем тэг что нам нужен
            # Ставим нужный словарь для получения значений
            key_dict = {0: 'S', 1: 'A', 2: 'B', 3: 'C', }
            tag = str(self._tags.get(self._data)) + str(key_dict[t - 1])
            # Теперь по значению этого тэга ищем значение в нашем словаре

            var = float(self.valuesbank['NOW'][tag])
            var = str(var)

        return var.encode()

    # значения профиля мощности
    def __get_bytes_for_PowerProfQpQmPpPm(self, t):  # power profile values

        time.sleep(self.respondtimeout)
        global times
        times = 1
        if self.Config.get(random) == '1':
            var = "%.2f" % (100 * random.random())
        else:
            tag = str(self._tags.get(self._data))
            # Теперь по значению этого тэга ищем значение в нашем словаре
            var = float(self.valuesbank['NOW'][tag]) / 1000
            var = str(var)
        return var.encode()

    # -----------------------------------------------------------------------------------------------------------------
    # Методы генерации данных

    # Серийник
    def __get_counter_snumber(self, t):  # seril number

        global times
        times = 1
        # ЕСЛИ мы не спустили серийник сверху - то используем стоковый

        if self.serial is None:
            serial = str(self.Config.get("snumber")).encode()
        else:
            serial = str(self.serial)
            serial = serial.encode()

        return serial

    # Номер модели

    def __get_counter_model(self, t):  # counter model

        global times
        times = 1
        # Параметр котоырй парсится из настроек - Couters
        # Подробнее смотри протокол энергомеры - Команда MODEL
        # model =str(self._counter.model)
        model = self.model
        return model.encode()

    # energy values - ПОКАЗАТЕЛИ ЭНЕРГИИ
    def __get_bytes_for_energy_and_set_times(self, t):  # energy values
        # А теперь очень важная вещь - пытаемся вытащить из команды значения что идут в скобках
        global times
        times = 6
        if self.Config.get(random) == '1':
            var = "%.3f" % (1000 * random.random())
        else:
            tag = str(self._tags.get(self._data)) + str(t - 1)

            query = 'Value[@code="' + tag + '"]'
            var = str(valuesbank.find(query).text)
        return var.encode()

    # частота
    def __get_frequ(self, t):  # frequency

        global times
        times = 1
        if self.Config.get(random) == '1':
            return b'50.00'
        else:
            tag = str(self._tags.get(self._data))
            # Теперь по значению этого тэга ищем значение в нашем словаре

            var = float(self.valuesbank['NOW'][tag])
            var = str(var)

            return var.encode()

    # общие значения для других тегов
    def __get_bytes_general_and_set_times(self, t):  # general values for other tags

        global times
        times = 3
        if self.Config.get(random) == '1':
            return str("%.3f" % random.random()).encode()
        else:
            tag = str(self._tags.get(self._data)) + str(t - 1)
            query = 'Value[@code="' + tag + '"]'
            var = str(valuesbank.find(query).text)
            return var.encode()

    # общие случайные значения для неподдерживаемых запросов и тегов
    def get_random_bytes(self, test=1, t=1):  # general random values for unsupported requests and tags

        global times
        times = 1
        var = "%.3f" % random.random()
        return var.encode()

    def __get_taver(self, t):  # taver
        """Период интегрирования, мин - Интервал времени усреднения значений профиля нагрузки"""

        global times
        times = 1
        cTime = self.valuesbank['cTime']
        cTime = str(cTime)
        return cTime.encode()

    def __get_NGRAP(self, t):
        """
        Количество суточных профилей нагрузки, хранимых в счетчике при заданном времени усреднения TAVER
         ПОКА НЕ ИСПОЛЬЗУЕТСЯ -
        """

        NGRAP = 99
        NGRAP = str(NGRAP)
        return NGRAP.encode()

    # trsum
    def __get_trsum(self, t):  # trsum
        'РАЗРЕШЕНИЕ НА ПЕРЕХОД НА ЗИМНЕЕ ВРЕМЯ'

        global times
        times = 1

        # Здесь - берем из наших настроек
        isDst = self.valuesbank['isDst']

        # ЗДЕСЬ берем и меняем булевы параметры на 1 и 0
        if isDst:
            isDst = 1

        else:
            isDst = 0

        isDst = isDst.to_bytes(length=2, byteorder='big')
        return isDst
        # isDst = str(isDst)
        # return isDst.encode()

    def __get_pacce(self, t):

        global times
        times = 1
        return b'01'

    # Коэффициент преобразования по напряжению
    def __get_kU(self, t):
        global times
        times = 1
        values = float(self.valuesbank['NOW']['kU'])
        values = str(values)
        return values.encode()

    # Коэффициент преобразования по току
    def __get_kI(self, t):
        global times
        times = 1
        values = float(self.valuesbank['NOW']['kI'])
        values = str(values)
        return values.encode()

    # -----------------------------------------------------------------------------------------------------------------
    # ----------------------------------        МЕТОДЫ ДЛЯ ЖУРНАЛОВ    ------------------------------------------------
    # -----------------------------------------------------------------------------------------------------------------
    def __get_JournalValues(self, t):
        """
        Метод для работы с ЖУРНАЛАМИ

        :param t:
        :return:
        """
        global times
        times = len(self.valuesbank['Journal'])

        # Получаем ТЭГ
        tag = str(self.tags.get(self.data))
        # Теперь по значению этого тэга ищем значение в нашем словаре
        values = str
        # values_list = str(self.valuesbank[tag])
        # for i in values_list:
        #     values = values + '(' + str(values_list[i]) + ')'
        values = str(self.valuesbank[tag][t - 1])

        return values.encode()

    # -----------------------------------------------------------------------------------------------------------------
    # текущая дата
    def __datenow(self, t):  # current date

        # time.sleep(self.respondtimeout)
        # global times
        # times = 1
        # if self.datecheck == 1:
        #     if self.datecheckcount == 1:
        #         today = date.fromtimestamp(1441043940)
        #         # self.datecheckcount = 2
        #     if self.datecheckcount == 2:
        #         today = date.fromtimestamp(1441054800)
        #         # self.datecheckcount = 3
        #     if self.datecheckcount == 3:
        #         today = date.fromtimestamp(1441054800)
        #         # self.datecheckcount = 4
        #     if self.datecheckcount == 4:
        #         today = date.fromtimestamp(1441054800)
        #         self.datecheckcount = 0
        # else:
        today = date.today()
        today = self.time_now.date()

        self.datecheckcount += 1

        return str(today.strftime("0%w.%d.%m.%y")).encode()

    # Текущее время
    def __timenow(self, t):  # current time

        global times
        times = 1
        # time.sleep(self.respondtimeout)
        # if self.datecheck == 1:
        #     now = datetime.fromtimestamp(2)
        # elif self.datecheck == 2:
        #     now = datetime.fromtimestamp(1)
        # else:

        # self.time_now = datetime.now()

        # Время при инициализации
        now = self.time_now.time()
        # Время сейчас
        # now = datetime.now().time()

        # ЗАПИСЫВАЕМ ВРЕМЯ
        # А в нашей команде его обновляем
        self.time_now = datetime.now()

        return str(now.strftime("%H:%M:%S")).encode()

    # Запись в файл текущего времени - ЭТО ОЧЕНЬ ВАЖНО

    def record_timenow(self):

        # Теперь переводим все это в Unixtime
        Unix_time = self.time_now.timestamp()
        # Делаем словарь
        timestamp_dict = {'time': int(Unix_time)}
        # Переводим в JSON
        timestamp_json = json.dumps(timestamp_dict)
        # А После записываем
        path_values = path + '/Counters/' + 'Meter_Timestamp.json'
        a = open(path_values, 'w')
        a.write(timestamp_json)
        a.close()

    # Список типов команд
    cmdbank = {
        # Команда тип - Привет
        b'/': __reqhello,
        #  Команда тип - Сообщение
        ack: __confirm,
        #  Команда тип - Обмен данными
        soh: __prog
    }
    # Добавляем значение ключа пустота (Если ничего не спарсили) на неправильный запрос
    cmdbank.setdefault(None, __empty)

    # Список ассоциаций различных запросов типов данных и ссылок на методы, что их формируют - Протокол ЭНЕРГОМЕРА
    _args = {
        # Дата
        b'DATE_': __datenow,
        # Время
        b'TIME_': __timenow,
        # Модель
        b'MODEL': __get_counter_model,
        # Серийный номер
        b'SNUMB': __get_counter_snumber,
        # Разрешение на переход на зимнее время
        b'TRSUM': __get_trsum,

        # Коэффициент трансформации трансформатора в первичной цепи напряжения (от 1 до 10000)
        b'FCVOL': __get_kU,
        # Коэффициент трансформации трансформатора в первичной цепи тока (от 1 до 10000)
        b'FCCUR': __get_kI,
        # Количество суточных профилей нагрузки, хранимых в счетчике при заданном времени усреднения TAVER
        b'NGRAP': __get_NGRAP,
        # Частота сети
        b'FREQU': __get_frequ,

        # Мгновенное значение фазной мощности - Активная
        b'POWPP': __get_bytes_for_Power_PA_PB_PC,
        # Мгновенное значение фазной мощности - Реактивная
        b'POWPQ': __get_bytes_for_PowerABC,
        # Мгновенное значение суммарной мощности - Активная
        b'POWEP': __get_bytes_for_PowerPS,
        # Мгновенное значение фазной мощности - Реактивная
        b'POWEQ': __get_bytes_for_PowerQS,

        # Коэффициенты мощности суммарный и по фазно
        b'COS_f': __get_bytes_for_Cos,

        # Действующее значение напряжения
        b'VOLTA': __get_bytes_for_Volts,
        # Действующее значение тока
        b'CURRE': __get_bytes_Current,

        # Углы между векторами напряжений фаз.
        b'CORUU': __get_bytes_for_Angles,

        # Значение энергии в кВт*ч - Мгновенный - А+
        b'ET0PE': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - Мгновенный - A-
        b'ET0PI': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - Мгновенный - R+
        b'ET0QE': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - Мгновенный - R-
        b'ET0QI': __get_bytes_for_energy_and_set_times_by_El_Energy,

        # Значение энергии в кВт*ч - конец Суток - A+
        b'ENDPE': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - конец Суток - A-
        b'ENDPI': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - конец Суток  - R+
        b'ENDQE': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - конец Суток  - R-
        b'ENDQI': __get_bytes_for_energy_and_set_times_by_El_Energy,

        # Значение энергии в кВт*ч - конец Месяца - A+
        b'ENMPE': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - конец Месяца - A-
        b'ENMPI': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - конец Месяца - R+
        b'ENMQE': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - конец Месяца - R-
        b'ENMQI': __get_bytes_for_energy_and_set_times_by_El_Energy,

        # Значение энергии в кВт*ч - за Сутки - A+
        b'EADPE': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - за Сутки - A-
        b'EADPI': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - за Сутки - R+
        b'EADQE': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - за Сутки - R-
        b'EADQI': __get_bytes_for_energy_and_set_times_by_El_Energy,

        # Значение энергии в кВт*ч - за Месяц - A+
        b'EAMPE': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - за Месяц - A-
        b'EAMPI': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - за Месяц - R+
        b'EAMQE': __get_bytes_for_energy_and_set_times_by_El_Energy,
        # Значение энергии в кВт*ч - за Месяц - R-
        b'EAMQI': __get_bytes_for_energy_and_set_times_by_El_Energy,

        # Энергия, накопленная в текущих сутках - A+
        b'ECDPE': __get_bytes_for_energy_and_set_times,
        # Энергия, накопленная в текущих сутках - A-
        b'ECDPI': __get_bytes_for_energy_and_set_times,
        # Энергия, накопленная в текущих сутках - R+
        b'ECDQE': __get_bytes_for_energy_and_set_times,
        # Энергия, накопленная в текущих сутках - R-
        b'ECDQI': __get_bytes_for_energy_and_set_times,

        # Энергия, накопленная в текущем месяце - A+
        b'ECMPE': __get_bytes_for_energy_and_set_times,
        # Энергия, накопленная в текущем месяце - A-
        b'ECMPI': __get_bytes_for_energy_and_set_times,
        # Энергия, накопленная в текущем месяце - R+
        b'ECMQE': __get_bytes_for_energy_and_set_times,
        # Энергия, накопленная в текущем месяце - R-
        b'ECMQI': __get_bytes_for_energy_and_set_times,

        # Профиль нагрузки (Мощности) - P+
        b'GRAPE': __get_bytes_for_PowerProfQpQmPpPm,
        # Профиль нагрузки (Мощности) - P-
        b'GRAPI': __get_bytes_for_PowerProfQpQmPpPm,
        # Профиль нагрузки (Мощности) - Q+
        b'GRAQE': __get_bytes_for_PowerProfQpQmPpPm,
        # Профиль нагрузки (Мощности) - Q-
        b'GRAQI': __get_bytes_for_PowerProfQpQmPpPm,

        # Период интегрирования, мин - Интервал времени усреднения значений профиля нагрузки
        b'TAVER': __get_taver,

        #
        # Кольцевой буфер - журналы электросчетчика:
        # Счетчик-указатель последней записи в кольцевом буфере журнала программирования счетчика. Отсчет с нуля
        b'PACCE': __get_pacce,
        # Счетчик-указатель последней записи в кольцевом буфере журнала вскрытий электронной пломбы. Отсчет с нуля
        b'PLOCK': __get_pacce,
        # Счетчик-указатель последней записи в кольцевом буфере журнала фиксации отказов в доступе. Отсчет с нуля
        b'PDENI': __get_pacce,
        # Счетчик-указатель последней записи в кольцевом буфере журнала состояния фаз счетчика. Отсчет с нуля
        b'PPHAS': __get_pacce,

        # ВЫХОД ЗА ПРЕДЕЛЫ ФАЗОВОГО ЗНАЧЕНИЯ
        b'JOVER': __get_JournalValues,
        # Фаза вкл/выкл
        b'PHASE': __get_JournalValues,
        # Корекция часов
        b'JCORT': __get_JournalValues,
        # вскрытие счетчика
        b'DENIA': __get_JournalValues,
        # Электронная пломба - плока выдает ошибку
        b'ELOCK': __get_JournalValues,
        # Журанл программирования
        b'ACCES': __get_JournalValues,

    }
