# Здесь основной файл запуска





class VirtualMeterManager:
    """
    Основной класс Менеджер нашего виртуального счетчика
    """

    # Это наш виртуальный счетчик
    _Virtual_Meter = None
    # TCP Сервер
    _TCP = None
    # COM Порт
    _COM = None
    def __init__(self,  Setup_config:[None, dict] = None,
                        Meter_config:[None, dict] = None,
                        Meter_values:[None, dict] = None
                 ):
        """
        При Объявлении класса нам необходимо:
        - Конфиг запуска Портов\Серверов коннект
        - Конфиг счетчика
        - Значения счетчика, что отправляем

        Если что-то из этого не задано - То печаль
        """


    def _Create_Meter(self, Meter_config, Meter_values):
        """
        Здесь создаем объект нашего Virtual Meter - Виртуального счетчика
        """

        self._Virtual_Meter =
class Setup:

    port = 5555

    def __init__(self, port=5555):
        self.port = port
        self._run_up_server()

    def _run_up_server(self):
        from Server_Meter import SocketMeters

        server = SocketMeters(self.port)



lol = Setup()

