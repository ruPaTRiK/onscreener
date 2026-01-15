from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout, QVBoxLayout, QMenu, QHBoxLayout, QPushButton
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QAction
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint
from core.base_window import OverlayWindow
from games.tic_tac_toe.logic import TicTacToeLogic
from core.emote_widget import FloatingEmote


class DrawingAnimation(QWidget):
    def __init__(self, parent, rect, symbol, on_finish):
        super().__init__(parent)
        self.setGeometry(rect)
        self.symbol = symbol
        self.on_finish = on_finish
        self.progress = 0  # 0.0 to 1.0
        self.show()

        # Таймер анимации
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)  # ~60 FPS

    def animate(self):
        self.progress += 0.05  # Скорость анимации
        if self.progress >= 1.0:
            self.progress = 1.0
            self.timer.stop()
            self.on_finish()
            self.deleteLater()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        pen_width = max(3, min(w, h) // 15)

        margin = int(min(w, h) * 0.25)

        if self.symbol == 'X':
            pen = QPen(QColor("#4FC3F7"))
            pen.setWidth(pen_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)

            # Рисуем две линии последовательно
            # Первая линия (0.0 - 0.5), Вторая (0.5 - 1.0)

            # Линия 1: \
            p1_end = min(self.progress * 2, 1.0)
            if p1_end > 0:
                x1, y1 = margin, margin
                x2 = margin + (w - 2 * margin) * p1_end
                y2 = margin + (h - 2 * margin) * p1_end
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

            # Линия 2: /
            if self.progress > 0.5:
                p2_end = (self.progress - 0.5) * 2
                x1, y1 = w - margin, margin
                x2 = (w - margin) - (w - 2 * margin) * p2_end
                y2 = margin + (h - 2 * margin) * p2_end
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        elif self.symbol == 'O':
            pen = QPen(QColor("#FF5252"))
            pen.setWidth(pen_width)
            painter.setPen(pen)

            # Рисуем дугу (угол в 1/16 градуса)
            # Полный круг = 360 * 16 = 5760
            span_angle = int(5760 * self.progress)

            rect = QRect(margin, margin, w - 2 * margin, h - 2 * margin)
            painter.drawArc(rect, 90 * 16, -span_angle)  # Начинаем сверху (90 град)


class TicTacToeGame(OverlayWindow):
    def __init__(self, is_online=False, is_host=True, network_client=None):
        super().__init__()
        self.logic = TicTacToeLogic()
        self.resize(400, 450)  # Компактный размер

        self.is_online = is_online
        self.network = network_client
        self.my_mark = 'X'
        if self.is_online:
            self.my_mark = 'X' if is_host else 'O'

        self.hidden_cell = None

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

        header_layout = QHBoxLayout()
        header_layout.addWidget(self.status_label)

        self.btn_emote = QPushButton("😀")
        self.btn_emote.setFixedSize(40, 40)
        self.btn_emote.setStyleSheet("background: rgba(255,255,255,30); border-radius: 20px; font-size: 20px;")
        self.btn_emote.clicked.connect(self.show_emote_menu)
        header_layout.addWidget(self.btn_emote)

        self.main_layout.addLayout(header_layout)

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

    def closeEvent(self, event):
        super().closeEvent(event)

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
                symbol = self.logic.turn

                if self.logic.make_move(row, col):
                    # Отправка хода
                    if self.is_online and self.network:
                        # Формат: "r,c" (так как это строка data)
                        self.network.send_json({"type": "game_move", "data": f"{row},{col}"})

                    self.start_animation(row, col, symbol)

    def _update_ui(self):
        # 1. Текст статуса
        if not self.logic.game_over:
            if self.is_online:
                x_suf = " (Вы)" if self.my_mark == 'X' else " (Соперник)"
                o_suf = " (Вы)" if self.my_mark == 'O' else " (Соперник)"
            else:
                x_suf = o_suf = ""

            text = f"Ход: Крестики{x_suf}" if self.logic.turn == 'X' else f"Ход: Нолики{o_suf}"
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

                should_draw = True
                if self.hidden_cell == (row, col):
                    should_draw = False

                if should_draw:
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

                symbol = self.logic.turn
                self.logic.make_move(r, c)

                self.start_animation(r, c, symbol)
            except:
                pass
        elif message == "restart_cmd":
            self.logic.reset_game()
            self._update_ui()

        if isinstance(message, dict) and message.get("type") == "game_emote":
            emoji = message.get("emoji")
            self.show_floating_emote(emoji, is_mine=False)

    def swap_sides(self, new_color):
        self.my_mark = 'X' if new_color == 'white' else 'O'

        self.logic.reset_game()
        self._update_ui()

    def start_animation(self, r, c, symbol):
        # 1. Скрываем реальную клетку
        self.hidden_cell = (r, c)
        self._update_ui()

        # 2. Находим координаты виджета
        label = self.cells[(r, c)]
        rect = label.geometry()
        offset = self.board_container.pos()
        final_rect = QRect(rect.topLeft() + offset, rect.size())

        # 3. Создаем аниматор
        DrawingAnimation(self, final_rect, symbol, self.finish_animation)

    def finish_animation(self):
        self.hidden_cell = None
        self._update_ui()

    def show_emote_menu(self):
        menu = QMenu(self)
        # Стиль меню
        menu.setStyleSheet("""
            QMenu { background-color: #2c3e50; color: white; border: 1px solid #555; }
            QMenu::item { padding: 5px 20px; font-size: 24px; }
            QMenu::item:selected { background-color: #34495e; }
        """)

        emojis = ["👍", "😂", "😭", "🤔", "😡", "GG"]
        for em in emojis:
            action = QAction(em, self)
            action.triggered.connect(lambda ch, e=em: self.send_emote(e))
            menu.addAction(action)

        # Показываем под кнопкой
        menu.exec(self.btn_emote.mapToGlobal(QPoint(0, self.btn_emote.height())))

    def send_emote(self, emoji):
        # Показываем у себя
        self.show_floating_emote(emoji, is_mine=True)

        # Отправляем
        if self.is_online and self.network:
            self.network.send_json({"type": "game_emote", "emoji": emoji})

    def show_floating_emote(self, emoji, is_mine):
        center = self.rect().center()

        FloatingEmote(self, emoji, center)