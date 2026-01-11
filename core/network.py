import socket
import json
from PyQt6.QtCore import QThread, pyqtSignal

# IP СЕРВЕРА (Можно менять)
DEFAULT_SERVER_IP = "127.0.0.1"
DEFAULT_SERVER_PORT = 5555


class NetworkClient(QThread):
    json_received = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.client = None
        self.is_running = False

    def connect_auto(self):
        self.start()

    def run(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client.connect((DEFAULT_SERVER_IP, DEFAULT_SERVER_PORT))
            self.is_running = True
            self.connected.emit()

            while self.is_running:
                data = self.client.recv(4096)
                if not data: break

                parts = data.decode('utf-8').split('\n')
                for part in parts:
                    if part.strip():
                        try:
                            self.json_received.emit(json.loads(part))
                        except:
                            pass
        except Exception as e:
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
            except:
                self.is_running = False

    def disconnect(self):
        self.is_running = False
        if self.client: self.client.close()