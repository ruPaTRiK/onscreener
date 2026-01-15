from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt


class UpdateProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Обновление...")
        self.setFixedSize(350, 150)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.setModal(True)  # Блокирует остальной интерфейс

        # Стилизация (темная тема)
        self.setStyleSheet("""
            QDialog { background-color: #2c3e50; color: white; }
            QLabel { font-size: 14px; font-weight: bold; }
            QProgressBar {
                border: 2px solid #555;
                border-radius: 5px;
                text-align: center;
                color: white;
                background-color: #34495e;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
                width: 10px;
            }
        """)

        layout = QVBoxLayout(self)

        self.lbl_status = QLabel("Скачивание обновления...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        layout.addStretch()

    def set_progress(self, val):
        self.progress.setValue(val)

    def set_status(self, text):
        self.lbl_status.setText(text)