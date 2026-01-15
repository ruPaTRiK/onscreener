from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QComboBox,
                             QLineEdit, QPushButton, QHBoxLayout)
from PyQt6.QtCore import Qt


class ServerSelectDialog(QDialog):
    def __init__(self, parent, server_list):
        """server_list: список словарей [{'name':.., 'ip':..., 'port':..}]"""
        super().__init__(parent)
        self.setWindowTitle("Выбор сервера")
        self.setFixedSize(350, 200)
        self.setStyleSheet("background-color: #2c3e50; color: white;")

        self.result_ip = None
        self.result_port = 5555

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Доступные серверы:"))

        self.combo = QComboBox()
        self.combo.setStyleSheet("padding: 5px; background: #34495e; border: 1px solid #555;")
        self.combo.addItem("Свой сервер (Ручной ввод)", "custom")

        # Заполняем список
        for s in server_list:
            data_str = f"{s['ip']}:{s.get('port', 5555)}"
            self.combo.addItem(s['name'], data_str)

        self.combo.currentIndexChanged.connect(self.on_change)
        layout.addWidget(self.combo)

        # Поле для ручного ввода
        self.inp_ip = QLineEdit()
        self.inp_ip.setPlaceholderText("IP адрес")
        self.inp_ip.setStyleSheet("padding: 5px; background: #34495e; border: 1px solid #555;")
        layout.addWidget(self.inp_ip)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Подключиться")
        btn_ok.setStyleSheet("background: #27ae60; padding: 8px; border-radius: 5px;")
        btn_ok.clicked.connect(self.do_connect)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

        # Выбираем первый сервер из списка по умолчанию (индекс 1, т.к. 0 это Custom)
        if len(server_list) > 0:
            self.combo.setCurrentIndex(1)

    def on_change(self, idx):
        data = self.combo.currentData()
        if data == "custom":
            self.inp_ip.setEnabled(True)
            self.inp_ip.setVisible(True)
            self.inp_ip.clear()
        else:
            ip, port = data.split(":")
            self.inp_ip.setVisible(False)
            self.inp_ip.setEnabled(False)

    def do_connect(self):
        if self.combo.currentData() == "custom":
            self.result_ip = self.inp_ip.text()
            self.result_port = 5555
        else:
            ip, port = self.combo.currentData().split(":")
            self.result_ip = ip
            self.result_port = int(port)
        self.accept()