from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout, QVBoxLayout
from PyQt6.QtGui import QPixmap, QPainter, QBrush, QColor, QFont, QPen
from PyQt6.QtCore import Qt
from core.base_window import OverlayWindow
from games.checkers.logic import CheckersLogic


class CheckersGame(OverlayWindow):
    def __init__(self, is_online=False, is_host=True, network_client=None):
        super().__init__()
        self.logic = CheckersLogic()
        self.resize(600, 650)

        # --- СЕТЬ ---
        self.is_online = is_online
        self.network = network_client
        self.my_color = 'white'
        if self.is_online:
            self.my_color = 'white' if is_host else 'black'

        self.selected_piece = None
        self.valid_moves = []

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # Заголовок
        self.status_label = QLabel("Ход: Белые")
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

        # Контейнер доски
        self.board_container = QWidget()
        self.main_layout.addWidget(self.board_container)

        self.grid_layout = QGridLayout(self.board_container)
        self.grid_layout.setSpacing(0)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)

        self.cells = {}
        self._init_board_ui()
        self._update_ui()

    def showEvent(self, event):
        super().showEvent(event)
        # Когда окно показывается (show), Layout уже закончил работу.
        # Мы принудительно обновляем UI, чтобы шашки перерисовались под правильный размер.
        self._update_ui()

    def _init_board_ui(self):
        for row in range(8):
            for col in range(8):
                label = QLabel()
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setScaledContents(True)

                # Устанавливаем БАЗОВЫЙ цвет один раз. Больше CSS трогать не будем.
                color = "#D18B47" if (row + col) % 2 == 0 else "#FFCE9E"
                label.setStyleSheet(f"background-color: {color}; border: none;")

                self.grid_layout.addWidget(label, row, col)
                self.cells[(row, col)] = label

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if self._action is not None: return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.logic.game_over:
                if self.is_online:
                    self.network.send_json({"type": "restart_game"})
                else:
                    self.logic.reset_game()
                    self._update_ui()
                return

            if self.is_online and self.logic.turn != self.my_color:
                return

            board_pos = self.board_container.mapFrom(self, event.position().toPoint())
            w = self.board_container.width()
            h = self.board_container.height()

            if board_pos.x() < 0 or board_pos.y() < 0 or board_pos.x() > w or board_pos.y() > h:
                return

            col = int(board_pos.x() // (w / 8))
            row = int(board_pos.y() // (h / 8))

            if 0 <= row < 8 and 0 <= col < 8:
                self.on_cell_click(row, col)

    def _update_ui(self):
        # 1. Обновляем статус (текст сверху)
        if self.logic.turn == 'white':
            self.status_label.setText("Ход: Белые")
            self.status_label.setStyleSheet("""
                color: white; background-color: rgba(0, 0, 0, 150); 
                border-radius: 10px; padding: 5px; border: 2px solid white;
            """)
        else:
            self.status_label.setText("Ход: Черные")
            self.status_label.setStyleSheet("""
                color: black; background-color: rgba(255, 255, 255, 200); 
                border-radius: 10px; padding: 5px; border: 2px solid black;
            """)

        board = self.logic.board

        # Получаем размеры клетки
        cell_size_w = self.board_container.width() // 8
        cell_size_h = self.board_container.height() // 8
        if cell_size_w < 1: cell_size_w = 1
        if cell_size_h < 1: cell_size_h = 1

        # !!! ИСПРАВЛЕНИЕ МАСШТАБИРОВАНИЯ !!!
        # Размер шашки = 80% от меньшей стороны клетки
        # Это гарантирует пропорции при любом размере окна
        piece_diameter = int(min(cell_size_w, cell_size_h) * 0.8)
        if piece_diameter < 1: piece_diameter = 1

        for row in range(8):
            for col in range(8):
                label = self.cells[(row, col)]
                piece = board[row][col]

                # Создаем холст
                pixmap = QPixmap(cell_size_w, cell_size_h)
                pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                # --- ВЫДЕЛЕНИЕ (Зеленый квадрат) ---
                if self.selected_piece == (row, col):
                    painter.fillRect(0, 0, cell_size_w, cell_size_h, QColor("#76FF03"))
                    # Рамка выделения остается, она помогает понять, что выбрано
                    pen = QPen(QColor("green"))
                    pen.setWidth(2)
                    painter.setPen(pen)
                    painter.drawRect(0, 0, cell_size_w, cell_size_h)

                # --- ПОДСКАЗКИ (Точки) ---
                if (row, col) in self.valid_moves:
                    painter.setBrush(QBrush(QColor(0, 255, 0, 180)))
                    painter.setPen(Qt.PenStyle.NoPen)
                    cx, cy = cell_size_w // 2, cell_size_h // 2
                    r = int(min(cell_size_w, cell_size_h) * 0.15)  # Точка = 15% от клетки
                    painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

                # --- ШАШКА ---
                if piece != 0:
                    # Центрируем
                    offset_x = (cell_size_w - piece_diameter) // 2
                    offset_y = (cell_size_h - piece_diameter) // 2

                    # !!! УБИРАЕМ ОБВОДКУ !!!
                    painter.setPen(Qt.PenStyle.NoPen)

                    if piece in [1, 3]:  # Белые
                        painter.setBrush(QBrush(Qt.GlobalColor.white))
                    else:  # Черные
                        painter.setBrush(QBrush(Qt.GlobalColor.black))

                    painter.drawEllipse(offset_x, offset_y, piece_diameter, piece_diameter)

                    # Дамка (Золотая серединка)
                    if piece in [3, 4]:
                        painter.setBrush(QBrush(QColor("gold")))
                        cx, cy = cell_size_w // 2, cell_size_h // 2
                        r = int(piece_diameter * 0.25)  # 25% от размера шашки
                        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

                painter.end()
                label.setPixmap(pixmap)

    def on_cell_click(self, row, col):
        # 1. ПОПЫТКА СДЕЛАТЬ ХОД (если фигура выбрана и клетка валидна)
        if self.selected_piece and (row, col) in self.valid_moves:
            start_pos = self.selected_piece
            end_pos = (row, col)

            # Пытаемся походить в логике
            success = self.logic.move_piece(start_pos, end_pos)

            if success:
                # А. ОТПРАВЛЯЕМ ХОД В СЕТЬ (сразу, так как доска изменилась)
                if self.is_online and self.network:
                    data_str = f"{start_pos[0]},{start_pos[1]}:{end_pos[0]},{end_pos[1]}"
                    self.network.send_json({"type": "game_move", "data": data_str})

                # Б. ОБРАБОТКА СЕРИИ ВЗЯТИЙ (Мульти-джамп)
                if self.logic.lock_piece:
                    # Если нужно бить дальше - оставляем эту шашку выбранной
                    self.selected_piece = (row, col)
                    # Пересчитываем ходы только для неё
                    self.valid_moves = self.logic.get_valid_moves(row, col)
                else:
                    # Ход завершен, передаем очередь
                    self.selected_piece = None
                    self.valid_moves = []

            self._update_ui()
            return

        # 2. ВЫБОР ФИГУРЫ (если ничего не выбрано или кликнули на другую)
        piece = self.logic.board[row][col]
        if piece != 0:
            # Проверяем цвета
            is_white_piece = (piece in [1, 3])
            is_turn_white = (self.logic.turn == 'white')

            # Если сейчас не ход этого цвета - выходим
            if is_white_piece != is_turn_white:
                return

            # ОНЛАЙН ПРОВЕРКА: Нельзя выделять чужие фигуры
            if self.is_online:
                is_me_white = (self.my_color == 'white')
                if is_white_piece != is_me_white:
                    return

            # Если всё ок - выделяем
            self.selected_piece = (row, col)
            self.valid_moves = self.logic.get_valid_moves(row, col)

        else:
            # Клик в пустоту - снимаем выделение
            self.selected_piece = None
            self.valid_moves = []

        self._update_ui()

    def resizeEvent(self, event):
        self._update_ui()
        super().resizeEvent(event)

    def on_network_message(self, message):
        if message.startswith("move:"):
            try:
                coords = message.split(":")[1:]
                r1, c1 = map(int, coords[0].split(","))
                r2, c2 = map(int, coords[1].split(","))

                self.logic.move_piece((r1, c1), (r2, c2))
                self._update_ui()
            except:
                pass
        elif message == "restart_cmd":
            self.logic.reset_game()
            self._update_ui()