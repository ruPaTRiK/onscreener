from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont


class CoinFlipDialog(QDialog):
    # Сигналы для возврата выбора
    choice_made = pyqtSignal(str)  # "heads" / "tails"
    order_made = pyqtSignal(str)  # "first" / "second"

    def __init__(self, parent=None, mode="pick"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(400, 300)

        self.layout = QVBoxLayout(self)

        # Контейнер для красоты
        self.frame = QLabel()
        self.frame.setStyleSheet("""
            background-color: #2c3e50; 
            border: 2px solid #ecf0f1; 
            border-radius: 20px;
        """)
        self.layout.addWidget(self.frame)

        self.inner_layout = QVBoxLayout(self.frame)

        self.title = QLabel("Монетка")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.title.setStyleSheet("color: white; border: none;")
        self.inner_layout.addWidget(self.title)

        self.status = QLabel("...")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setFont(QFont("Arial", 40, QFont.Weight.Bold))
        self.status.setStyleSheet("color: gold; border: none;")
        self.inner_layout.addWidget(self.status)

        self.btn_layout = QHBoxLayout()
        self.inner_layout.addLayout(self.btn_layout)

        self.mode = mode
        if mode == "pick":
            self.setup_pick_ui()
        elif mode == "wait":
            self.title.setText("Соперник выбирает...")
            self.status.setText("⏳")

    def setup_pick_ui(self):
        self.title.setText("Орел или Решка?")
        b1 = QPushButton("Орел (Heads)")
        b2 = QPushButton("Решка (Tails)")

        # Явное подключение без цикла для надежности
        b1.setStyleSheet("background: #34495e; color: white; padding: 10px; border-radius: 5px;")
        b1.clicked.connect(lambda: self.emit_choice("heads"))
        self.btn_layout.addWidget(b1)

        b2.setStyleSheet("background: #34495e; color: white; padding: 10px; border-radius: 5px;")
        b2.clicked.connect(lambda: self.emit_choice("tails"))
        self.btn_layout.addWidget(b2)

    def setup_order_ui(self):
        while self.btn_layout.count():
            item = self.btn_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        self.title.setText("Вы победили! Ваш выбор:")
        b1 = QPushButton("Ходить 1-м")
        b2 = QPushButton("Ходить 2-м")

        b1.setStyleSheet("background: #27ae60; color: white; padding: 10px; border-radius: 5px;")
        b1.clicked.connect(lambda: self.emit_order("first"))
        self.btn_layout.addWidget(b1)

        b2.setStyleSheet("background: #27ae60; color: white; padding: 10px; border-radius: 5px;")
        b2.clicked.connect(lambda: self.emit_order("second"))
        self.btn_layout.addWidget(b2)

    def emit_choice(self, val):
        self.choice_made.emit(val)
        self.title.setText("Ждем броска...")
        # Скрываем кнопки
        for i in range(self.btn_layout.count()):
            self.btn_layout.itemAt(i).widget().hide()

    def emit_order(self, val):
        self.order_made.emit(val)
        self.accept()

    def start_animation(self, result, is_winner):
        # Анимация перебора
        self.anim_steps = 10
        self.final_result = result
        self.is_winner = is_winner
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate_step)
        self.timer.start(100)

    def animate_step(self):
        current = self.status.text()
        self.status.setText("O" if current != "O" else "P")  # Типа мелькание
        self.anim_steps -= 1
        if self.anim_steps <= 0:
            self.timer.stop()
            self.show_result()

    def show_result(self):
        text = "ОРЕЛ" if self.final_result == "heads" else "РЕШКА"
        self.status.setText(text)

        if self.is_winner:
            self.setup_order_ui()
        else:
            self.title.setText("Вы проиграли жеребьевку")
            QTimer.singleShot(2000, self.accept)  # Закрыть через 2 сек