from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout, QVBoxLayout
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QBrush
from PyQt6.QtCore import Qt, QRect
from core.base_window import OverlayWindow
from games.chess.logic import ChessLogic


class ChessGame(OverlayWindow):
    def __init__(self, is_online=False, is_host=True, network_client=None):
        super().__init__()
        self.logic = ChessLogic()
        self.resize(600, 650)

        # --- НАСТРОЙКИ СЕТИ ---
        self.is_online = is_online
        self.network = network_client
        self.my_color = 'white'  # По умолчанию (оффлайн)

        if self.is_online:
            self.my_color = 'white' if is_host else 'black'

        self.selected_piece = None
        self.valid_moves = []

        # Segoe UI Symbol должен быть в системе, иначе будут квадратики
        self.symbols = {
            'wK': '♔', 'wQ': '♕', 'wR': '♖', 'wB': '♗', 'wN': '♘', 'wP': '♙',
            'bK': '♚', 'bQ': '♛', 'bR': '♜', 'bB': '♝', 'bN': '♞', 'bP': '♟'
        }

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        self.status_label = QLabel("Ход: Белые")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.status_label.setStyleSheet(
            "color: white; background-color: rgba(0,0,0,150); border-radius: 10px; padding: 5px;")
        self.status_label.setFixedHeight(40)
        self.main_layout.addWidget(self.status_label)

        self.board_container = QWidget()
        self.main_layout.addWidget(self.board_container)

        self.grid_layout = QGridLayout(self.board_container)
        self.grid_layout.setSpacing(0)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)

        self.cells = {}
        self._init_board_ui()

    def _init_board_ui(self):
        for row in range(8):
            for col in range(8):
                label = QLabel()
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setScaledContents(True)
                color = "#F0D9B5" if (row + col) % 2 == 0 else "#B58863"
                label.setStyleSheet(f"background-color: {color}; border: none;")
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
            if self.is_online:
                if self.logic.turn != self.my_color:
                    return

            # Рестарт по клику после матча
            if self.logic.game_over:
                if self.is_online:
                    self.network.send_json({"type": "restart_game"})
                else:
                    self.logic.reset_game()
                    self._update_ui()
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
        if self.is_online:
            white_suffix = " (Вы)" if self.my_color == 'white' else " (Соперник)"
            black_suffix = " (Вы)" if self.my_color == 'black' else " (Соперник)"
        else:
            white_suffix = ""
            black_suffix = ""

        # 1. СТАТУС БАР
        if self.logic.game_over:
            if self.logic.winner == 'Draw':
                self.status_label.setText("ПАТ (Ничья) - Кликни для рестарта")
                self.status_label.setStyleSheet(
                    "color: yellow; background-color: rgba(0,0,0,200); border-radius: 10px; border: 2px solid yellow;")
            else:
                winner_ru = "Белые" if self.logic.winner == 'white' else "Черные"
                self.status_label.setText(f"МАТ! Победили {winner_ru}")
                self.status_label.setStyleSheet(
                    "color: #76FF03; background-color: rgba(0,0,0,200); border-radius: 10px; border: 2px solid #76FF03;")

        elif self.logic.is_check:
            turn_ru = "Белые" if self.logic.turn == 'white' else "Черные"
            self.status_label.setText(f"Ход: {turn_ru} (ШАХ!)")
            # Ярко красный фон при шахе
            self.status_label.setStyleSheet(
                "color: white; background-color: #d32f2f; border-radius: 10px; border: 3px solid white;")

        else:
            turn_ru = f"Белые{white_suffix}" if self.logic.turn == 'white' else f"Черные{black_suffix}"
            self.status_label.setText(f"Ход: {turn_ru}")
            # Обычный стиль
            if self.logic.turn == 'white':
                self.status_label.setStyleSheet(
                    "color: white; background-color: rgba(0,0,0,150); border-radius: 10px; border: 2px solid white;")
            else:
                self.status_label.setStyleSheet(
                    "color: black; background-color: rgba(255,255,255,200); border-radius: 10px; border: 2px solid black;")

        # 2. ДОСКА
        cell_w = self.board_container.width() // 8
        cell_h = self.board_container.height() // 8
        if cell_w < 1: cell_w = 1
        if cell_h < 1: cell_h = 1

        font_size = int(min(cell_w, cell_h) * 0.7)
        font = QFont("Segoe UI Symbol", font_size)

        for row in range(8):
            for col in range(8):
                label = self.cells[(row, col)]
                piece_code = self.logic.board[row][col]

                pixmap = QPixmap(cell_w, cell_h)
                pixmap.fill(Qt.GlobalColor.transparent)

                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)

                # Подсветка Короля при шахе (Красный фон под королем)
                if self.logic.is_check and piece_code.endswith('K'):
                    is_active_king = (piece_code.startswith('w') and self.logic.turn == 'white') or \
                                     (piece_code.startswith('b') and self.logic.turn == 'black')
                    if is_active_king:
                        painter.fillRect(0, 0, cell_w, cell_h, QColor(255, 0, 0, 150))

                # Обычное выделение
                if self.selected_piece == (row, col):
                    painter.fillRect(0, 0, cell_w, cell_h, QColor(0, 255, 0, 100))
                    pen = QPen(QColor("green"))
                    pen.setWidth(3)
                    painter.setPen(pen)
                    painter.drawRect(0, 0, cell_w, cell_h)

                # Подсказки
                if (row, col) in self.valid_moves:
                    painter.setBrush(QBrush(QColor(0, 255, 0, 180)))
                    painter.setPen(Qt.PenStyle.NoPen)
                    cx, cy = cell_w // 2, cell_h // 2
                    r = int(min(cell_w, cell_h) * 0.15)

                    if self.logic.board[row][col] != '':
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        pen = QPen(QColor(255, 0, 0, 180))
                        pen.setWidth(4)
                        painter.setPen(pen)
                        painter.drawEllipse(cx - r * 2, cy - r * 2, r * 4, r * 4)
                    else:
                        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

                if piece_code != '':
                    symbol = self.symbols[piece_code]
                    painter.setFont(font)
                    if piece_code.startswith('w'):
                        painter.setPen(QColor("white"))
                    else:
                        painter.setPen(QColor("black"))

                    rect = QRect(0, 0, cell_w, cell_h)
                    if piece_code.startswith('w'):
                        painter.setPen(QColor("black"))
                        painter.drawText(rect.adjusted(1, 1, 1, 1), Qt.AlignmentFlag.AlignCenter, symbol)
                        painter.setPen(QColor("white"))
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, symbol)

                painter.end()
                label.setPixmap(pixmap)

    def on_cell_click(self, row, col):
        start = self.selected_piece
        end = (row, col)

        if self.selected_piece and (row, col) in self.valid_moves:
            success = self.logic.move_piece(self.selected_piece, (row, col))
            if success:
                self.selected_piece = None
                self.valid_moves = []
                self._update_ui()
                if self.is_online and self.network:
                    # Формат: "r1,c1:r2,c2"
                    data_str = f"{start[0]},{start[1]}:{end[0]},{end[1]}"
                    self.network.send_json({"type": "game_move", "data": data_str})
            return

        piece = self.logic.board[row][col]
        if piece != '':
            color = piece[0]

            if self.is_online:
                is_mine = (color == 'w' and self.my_color == 'white') or \
                          (color == 'b' and self.my_color == 'black')
                if not is_mine: return

            if (self.logic.turn == 'white' and color == 'w') or \
                    (self.logic.turn == 'black' and color == 'b'):
                self.selected_piece = (row, col)
                self.valid_moves = self.logic.get_valid_moves(row, col)
        else:
            self.selected_piece = None
            self.valid_moves = []

        self._update_ui()

    def on_network_message(self, message):
        """Вызывается из Лаунчера при ходе соперника"""
        if message.startswith("move:"):
            try:
                # message = "move:6,4:4,4"
                coords = message.split(":")[1:]  # ['6,4', '4,4']
                r1, c1 = map(int, coords[0].split(","))
                r2, c2 = map(int, coords[1].split(","))

                # Применяем ход
                self.logic.move_piece((r1, c1), (r2, c2))
                self._update_ui()
            except Exception as e:
                print(f"Ошибка сети в игре: {e}")
        elif message == "restart_cmd":
            self.logic.reset_game()
            self._update_ui()