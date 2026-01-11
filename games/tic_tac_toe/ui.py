from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout, QVBoxLayout
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt
from core.base_window import OverlayWindow
from games.tic_tac_toe.logic import TicTacToeLogic


class TicTacToeGame(OverlayWindow):
    def __init__(self, is_online=False, is_host=True, network_client=None):
        super().__init__()
        self.logic = TicTacToeLogic()
        self.resize(400, 450)  # Компактный размер

        self.is_online = is_online
        self.network = network_client
        self.my_mark = 'X'
        if self.is_online:
            # Хост всегда Крестики (X), Гость - Нолики (O)
            self.my_mark = 'X' if is_host else 'O'

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # Статус бар сверху
        self.status_label = QLabel("Ход: Крестики (X)")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.status_label.setStyleSheet("""
            color: white; 
            background-color: rgba(0, 0, 0, 150); 
            border-radius: 10px;
            padding: 5px;
        """)
        self.status_label.setFixedHeight(40)
        self.main_layout.addWidget(self.status_label)

        # Контейнер для поля
        self.board_container = QWidget()
        self.main_layout.addWidget(self.board_container)

        self.grid_layout = QGridLayout(self.board_container)
        self.grid_layout.setSpacing(0)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)

        self.cells = {}
        self._init_board_ui()

    def _init_board_ui(self):
        for row in range(3):
            for col in range(3):
                label = QLabel()
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setScaledContents(True)
                # Делаем фон полупрозрачным черным, чтобы видеть границы
                label.setStyleSheet("background-color: rgba(0, 0, 0, 50); border: 2px solid rgba(255, 255, 255, 100);")
                self.grid_layout.addWidget(label, row, col)
                self.cells[(row, col)] = label

    def showEvent(self, event):
        super().showEvent(event)
        self._update_ui()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_ui()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self._action is not None: return

        if event.button() == Qt.MouseButton.LeftButton:
            # 1. ЛОГИКА РЕСТАРТА (Если игра окончена)
            if self.logic.game_over:
                if self.is_online:
                    # Если онлайн - шлем запрос на сервер
                    if self.network:
                        self.network.send_json({"type": "restart_game"})
                else:
                    # Если оффлайн - сбрасываем локально
                    self.logic.reset_game()
                    self._update_ui()
                return

            # 2. ПРОВЕРКА ОЧЕРЕДИ ХОДА (Для онлайн)
            if self.is_online and self.logic.turn != self.my_mark:
                return  # Ждем соперника

            # 3. ВЫЧИСЛЕНИЕ КООРДИНАТ
            board_pos = self.board_container.mapFrom(self, event.position().toPoint())
            w = self.board_container.width()
            h = self.board_container.height()

            if board_pos.x() < 0 or board_pos.y() < 0 or board_pos.x() > w or board_pos.y() > h:
                return

            col = int(board_pos.x() // (w / 3))
            row = int(board_pos.y() // (h / 3))

            # 4. СОВЕРШЕНИЕ ХОДА
            if 0 <= row < 3 and 0 <= col < 3:
                if self.logic.make_move(row, col):
                    self._update_ui()

                    # Отправка хода
                    if self.is_online and self.network:
                        # Формат: "r,c" (так как это строка data)
                        self.network.send_json({"type": "game_move", "data": f"{row},{col}"})

    def _update_ui(self):
        # 1. Текст статуса
        if not self.logic.game_over:
            text = "Ход: Крестики (X)" if self.logic.turn == 'X' else "Ход: Нолики (O)"
            self.status_label.setText(text)
            self.status_label.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150); border-radius: 10px;")
        else:
            if self.logic.winner == 'Draw':
                self.status_label.setText("Ничья! (Кликни для рестарта)")
                self.status_label.setStyleSheet(
                    "color: yellow; background-color: rgba(0, 0, 0, 180); border-radius: 10px;")
            else:
                winner_name = "Крестики" if self.logic.winner == 'X' else "Нолики"
                self.status_label.setText(f"Победили {winner_name}! (Кликни)")
                self.status_label.setStyleSheet(
                    "color: #76FF03; background-color: rgba(0, 0, 0, 180); border-radius: 10px;")

        # 2. Отрисовка поля
        cell_w = self.board_container.width() // 3
        cell_h = self.board_container.height() // 3
        if cell_w < 1: cell_w = 1
        if cell_h < 1: cell_h = 1

        for row in range(3):
            for col in range(3):
                label = self.cells[(row, col)]
                symbol = self.logic.board[row][col]

                pixmap = QPixmap(cell_w, cell_h)
                pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                # Если эта клетка часть победной линии - подсветим фон
                if (row, col) in self.logic.winning_line:
                    painter.fillRect(0, 0, cell_w, cell_h, QColor(0, 255, 0, 50))

                # Настройка линий (толщина зависит от размера окна)
                pen_width = max(3, min(cell_w, cell_h) // 15)

                if symbol == 'X':
                    pen = QPen(QColor("#4FC3F7"))  # Голубой цвет для X
                    pen.setWidth(pen_width)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    painter.setPen(pen)

                    margin = int(min(cell_w, cell_h) * 0.25)
                    painter.drawLine(margin, margin, cell_w - margin, cell_h - margin)
                    painter.drawLine(cell_w - margin, margin, margin, cell_h - margin)

                elif symbol == 'O':
                    pen = QPen(QColor("#FF5252"))  # Красный цвет для O
                    pen.setWidth(pen_width)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)

                    margin = int(min(cell_w, cell_h) * 0.25)
                    painter.drawEllipse(margin, margin, cell_w - margin * 2, cell_h - margin * 2)

                painter.end()
                label.setPixmap(pixmap)

    def on_network_message(self, message):
        # message: "move:1,2"
        if message.startswith("move:"):
            try:
                data = message.split(":")[1]  # "1,2"
                r, c = map(int, data.split(","))

                self.logic.make_move(r, c)
                self._update_ui()
            except:
                pass
        elif message == "restart_cmd":
            self.logic.reset_game()
            self._update_ui()