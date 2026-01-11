from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit,
                             QPushButton, QHBoxLayout, QCheckBox)
from PyQt6.QtCore import Qt


class CreateLobbyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создать комнату")
        self.setFixedSize(300, 200)
        self.setStyleSheet("background-color: #1E1E2E; color: #EAEAEA;")

        layout = QVBoxLayout(self)

        self.name_inp = QLineEdit("Игровая комната")
        self.name_inp.setPlaceholderText("Название лобби")
        self.name_inp.setStyleSheet("padding: 5px; border: 1px solid #3E3E50; border-radius: 7px;")
        layout.addWidget(QLabel("Название:"))
        layout.addWidget(self.name_inp)

        self.check_private = QCheckBox("Закрытая комната (Пароль)")
        self.check_private.toggled.connect(self.toggle_pass)
        layout.addWidget(self.check_private)

        self.pass_inp = QLineEdit()
        self.pass_inp.setPlaceholderText("Пароль")
        self.pass_inp.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_inp.setStyleSheet("padding: 5px; border: 1px solid #3E3E50; border-radius: 7px;")
        self.pass_inp.setEnabled(False)
        layout.addWidget(self.pass_inp)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Создать")
        btn_ok.setStyleSheet("background: #2ECC71; padding: 5px;")
        btn_ok.clicked.connect(self.accept)

        btn_cancel = QPushButton("Отмена")
        btn_cancel.setStyleSheet("background: #E74C3C; padding: 5px;")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def toggle_pass(self, checked):
        self.pass_inp.setEnabled(checked)

    def get_data(self):
        return {
            "name": self.name_inp.text(),
            "is_private": self.check_private.isChecked(),
            "password": self.pass_inp.text()
        }


class PasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Введите пароль")
        self.setFixedSize(250, 100)
        self.setStyleSheet("background-color: #1E1E2E; color: #EAEAEA;")

        layout = QVBoxLayout(self)
        self.inp = QLineEdit()
        self.inp.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp.setStyleSheet("padding: 5px; border: 1px solid #3E3E50; border-radius: 7px;")
        layout.addWidget(QLabel("Пароль комнаты:"))
        layout.addWidget(self.inp)

        btn = QPushButton("Войти")
        btn.setStyleSheet("background: #2ECC71; padding: 5px;")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_password(self):
        return self.inp.text()