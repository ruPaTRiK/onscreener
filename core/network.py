import socket
import json
from PyQt6.QtCore import QThread, pyqtSignal


class NetworkClient(QThread):
    json_received = pyqtSignal(dict)
    data_sent = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.client = None
        self.is_running = False
        # Переменные для хранения целевого адреса
        self.target_ip = "127.0.0.1"
        self.target_port = 5555

    # ЭТОТ МЕТОД ОБЯЗАТЕЛЕН
    def connect_to(self, ip, port):
        self.target_ip = ip
        self.target_port = int(port)

        # Если поток уже работает - останавливаем, чтобы перезапустить
        if self.isRunning():
            self.is_running = False
            if self.client:
                try:
                    # shutdown + close прерывают recv мгновенно
                    self.client.shutdown(socket.SHUT_RDWR)
                    self.client.close()
                except:
                    pass
            self.quit()

        self.start()  # Запускает run()

    def connect_auto(self):
        # Метод-заглушка, если где-то остался старый вызов
        self.start()

    def run(self):
        # Создаем НОВЫЙ сокет при каждом запуске потока
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.settimeout(10)  # Таймаут 10 сек, чтобы не висело вечно

        try:
            self.client.connect((self.target_ip, self.target_port))
            self.client.settimeout(None)  # Убираем таймаут для работы

            self.is_running = True
            self.connected.emit()

            while self.is_running:
                try:
                    data = self.client.recv(4096)
                    if not data: break

                    parts = data.decode('utf-8').split('\n')
                    for part in parts:
                        if part.strip():
                            try:
                                self.json_received.emit(json.loads(part))
                            except:
                                pass
                except socket.error:
                    break

        except Exception as e:
            print(f"DEBUG: Ошибка подключения в run: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.is_running = False
            self.disconnected.emit()
            if self.client: self.client.close()

    def send_json(self, data):
        if self.is_running and self.client:
            try:
                msg = json.dumps(data) + "\n"
                self.client.send(msg.encode('utf-8'))
                self.data_sent.emit(data)
            except:
                self.is_running = False

    def disconnect(self):
        self.is_running = False
        if self.client: self.client.close()