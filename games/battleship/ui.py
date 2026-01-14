from PyQt6.QtWidgets import QWidget, QLabel, QGridLayout, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QBrush
from PyQt6.QtCore import Qt, QRect, QPoint
from core.base_window import OverlayWindow
from games.battleship.logic import BattleshipLogic


class BattleshipGame(OverlayWindow):
    def __init__(self, is_online=False, is_host=True, network_client=None):
        super().__init__()
        self.logic = BattleshipLogic()
        self.resize(1000, 600)
        self.setMinimumSize(800, 500)

        self.is_online = is_online
        self.network = network_client

        # is_host=True значит "Белые" (или тот, кто выиграл право первого хода)
        self.is_first_player = is_host if is_host is not None else True
        self.opponent_ready = False

        self.dragging_ship_id = None
        self.drag_orientation = 'h'

        self.can_restart = False

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.layout.addStretch()
        self.ready_btn = QPushButton("Я ГОТОВ К БОЮ")
        self.ready_btn.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.ready_btn.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; border-radius: 10px; padding: 10px; }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:disabled { background-color: #555; color: #aaa; }
        """)
        self.ready_btn.clicked.connect(self.on_ready_click)
        self.ready_btn.setFixedWidth(200)
        self.ready_btn.hide()

        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(self.ready_btn)
        h_layout.addStretch()
        self.layout.addLayout(h_layout)

        # if self.network:
        #     self.network.json_received.connect(self.on_network_message)

    # --- ГЛАВНОЕ ИСПРАВЛЕНИЕ ТУТ ---
    def _update_ui(self):
        """Вызывается из main.py при рестарте (restart_cmd)"""
        # Если логика сбросилась в setup, нужно почистить UI-флаги
        if self.logic.phase == 'setup':
            self.opponent_ready = False
            self.dragging_ship_id = None
            self.ready_btn.setText("Я ГОТОВ К БОЮ")
            self.check_ready_status()

            self.can_restart = False

        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        dock_height = int(h * 0.2)
        play_area_h = h - dock_height
        cell_size = min(w // 25, play_area_h // 12)
        if cell_size < 1: cell_size = 1
        board_px = cell_size * 10

        left_x = int(w * 0.1)
        top_y = int((play_area_h - board_px) / 2)
        right_x = int(w * 0.6)

        self.left_rect = QRect(left_x, top_y, board_px, board_px)
        self.right_rect = QRect(right_x, top_y, board_px, board_px)
        self.cell_size = cell_size
        self.dock_rect = QRect(0, h - dock_height, w, dock_height)

        self.draw_board(painter, self.left_rect, "МОЙ ФЛОТ", is_mine=True)
        self.draw_board(painter, self.right_rect, "ВРАГ", is_mine=False)

        if self.logic.phase == 'setup':
            self.draw_dock(painter)
        if self.dragging_ship_id:
            self.draw_dragging_ship(painter)

        self.draw_status(painter, w)

    def draw_status(self, p, w):
        p.setPen(QColor("white"))
        p.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        text = ""

        if self.logic.game_over:
            if self.logic.winner == 'me':
                text = "ПОБЕДА! (Кликни для реванша)"
                p.setPen(QColor("#2ecc71"))
            else:
                text = "ПОРАЖЕНИЕ! (Кликни для реванша)"
                p.setPen(QColor("#e74c3c"))
        elif self.logic.phase == 'setup':
            text = "Расстановка: Перетащи корабли (ПКМ/Ctrl - поворот)"
        elif self.logic.phase == 'wait_ready':
            text = "Флот готов. Нажми кнопку внизу."
        elif self.logic.phase == 'wait_opp':
            text = "Ожидание соперника..."
        elif self.logic.phase == 'playing':
            if self.logic.my_turn:
                text = "ВАШ ХОД! Атакуйте правое поле!"
                p.setPen(QColor("#2ecc71"))
            else:
                text = "Ход соперника..."
                p.setPen(QColor("#e74c3c"))

        p.drawText(0, 30, w, 40, Qt.AlignmentFlag.AlignCenter, text)

    def draw_board(self, p, rect, title, is_mine):
        p.setPen(QColor("white"))
        p.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        p.drawText(rect.x(), rect.y() - 10, rect.width(), 20, Qt.AlignmentFlag.AlignCenter, title)

        p.setBrush(QBrush(QColor(0, 0, 0, 80)))
        p.setPen(QPen(QColor(255, 255, 255, 50), 1))
        p.drawRect(rect)
        cs = self.cell_size

        for i in range(11):
            p.drawLine(rect.x(), rect.y() + i * cs, rect.x() + 10 * cs, rect.y() + i * cs)
            p.drawLine(rect.x() + i * cs, rect.y(), rect.x() + i * cs, rect.y() + 10 * cs)

        for r in range(10):
            for c in range(10):
                x, y = rect.x() + c * cs, rect.y() + r * cs
                if is_mine:
                    val = self.logic.my_board[r][c]
                    if val > 0:
                        p.fillRect(x + 2, y + 2, cs - 4, cs - 4, QColor("#3498db"))
                    elif val == -2:
                        p.fillRect(x + 2, y + 2, cs - 4, cs - 4, QColor("#e74c3c"))
                        self._draw_cross(p, x, y, cs)
                    elif val == -3:
                        p.fillRect(x + 2, y + 2, cs - 4, cs - 4, QColor("#555"))
                        self._draw_cross(p, x, y, cs)
                    elif val == -1:
                        p.setBrush(QBrush(QColor("white")))
                        p.drawEllipse(x + cs // 2 - 3, y + cs // 2 - 3, 6, 6)
                else:
                    val = self.logic.enemy_view[r][c]
                    if val == 1:
                        p.setBrush(QBrush(QColor("white")))
                        p.drawEllipse(x + cs // 2 - 3, y + cs // 2 - 3, 6, 6)
                    elif val == 2:
                        p.fillRect(x + 2, y + 2, cs - 4, cs - 4, QColor("#e74c3c"))
                        self._draw_cross(p, x, y, cs)
                    elif val == 3:
                        p.fillRect(x + 2, y + 2, cs - 4, cs - 4, QColor("#555"))
                        self._draw_cross(p, x, y, cs)
                        p.setPen(QPen(QColor("red"), 2))
                        p.drawRect(x + 1, y + 1, cs - 2, cs - 2)

    def _draw_cross(self, p, x, y, cs):
        p.setPen(QPen(QColor("black"), 2))
        p.drawLine(x, y, x + cs, y + cs)
        p.drawLine(x + cs, y, x, y + cs)

    def draw_dock(self, p):
        start_x = 50
        base_y = self.dock_rect.y() + 30
        cs = self.cell_size
        for ship in self.logic.fleet_config:
            sid = ship["id"]
            if not self.logic.is_ship_placed(sid) and sid != self.dragging_ship_id:
                width = ship["size"] * cs
                p.fillRect(start_x, base_y, width, cs, QColor("#95a5a6"))
                p.setPen(QColor("white"))
                p.drawRect(start_x, base_y, width, cs)
                start_x += width + 20

    def draw_dragging_ship(self, p):
        cursor_pos = self.mapFromGlobal(self.cursor().pos())
        x, y = cursor_pos.x(), cursor_pos.y()
        ship_data = next(s for s in self.logic.fleet_config if s["id"] == self.dragging_ship_id)
        size = ship_data["size"]
        cs = self.cell_size
        w, h = (size * cs, cs) if self.drag_orientation == 'h' else (cs, size * cs)
        p.setOpacity(0.7)
        p.fillRect(x - w // 2, y - h // 2, w, h, QColor("#2ecc71"))
        p.setOpacity(1.0)

    def mousePressEvent(self, event):
        # 1. РЕСТАРТ
        if self.logic.game_over:
            if self.can_restart and event.button() == Qt.MouseButton.LeftButton:
                if self.is_online and self.network:
                    self.network.send_json({"type": "restart_game"})
            return

        # 2. ИГРА
        if self.logic.phase == 'playing':
            if event.button() == Qt.MouseButton.LeftButton and self.logic.my_turn:
                pos = event.position().toPoint()
                if self.right_rect.contains(pos):
                    col = (pos.x() - self.right_rect.x()) // int(self.cell_size)
                    row = (pos.y() - self.right_rect.y()) // int(self.cell_size)

                    if self.logic.enemy_view[row][col] == 0:
                        if self.is_online and self.network:
                            self.network.send_json({
                                "type": "game_move",
                                "sub_type": "shot",
                                "r": row, "c": col
                            })
            super().mousePressEvent(event)
            return

        # 3. РАССТАНОВКА
        if self.logic.phase == 'setup':
            modifiers = event.modifiers()
            if self.dragging_ship_id and (modifiers & Qt.KeyboardModifier.ControlModifier):
                self.drag_orientation = 'v' if self.drag_orientation == 'h' else 'h'
                self.update()
                return

            pos = event.position().toPoint()

            # Взять из дока
            if self.dock_rect.contains(pos):
                sid = self.get_ship_at_dock(pos)
                if sid:
                    self.dragging_ship_id = sid
                    self.drag_orientation = 'h'
                    self.update()
                    return

            # Взять с поля
            if self.left_rect.contains(pos):
                c = (pos.x() - self.left_rect.x()) // int(self.cell_size)
                r = (pos.y() - self.left_rect.y()) // int(self.cell_size)
                sid = self.logic.my_board[r][c]
                if sid != 0:
                    self.dragging_ship_id = sid
                    data = self.logic.placed_ships[sid]
                    self.drag_orientation = data["ori"]
                    self.logic.remove_ship(sid)
                    self.check_ready_status()
                    self.update()
                    return

            # Поставить
            if self.dragging_ship_id:
                if self.left_rect.contains(pos):
                    ship_d = next(s for s in self.logic.fleet_config if s["id"] == self.dragging_ship_id)
                    dw = (ship_d["size"] * self.cell_size) if self.drag_orientation == 'h' else self.cell_size
                    dh = self.cell_size if self.drag_orientation == 'h' else (ship_d["size"] * self.cell_size)
                    cx = pos.x() - dw // 2
                    cy = pos.y() - dh // 2

                    c = round((cx - self.left_rect.x()) / self.cell_size)
                    r = round((cy - self.left_rect.y()) / self.cell_size)

                    if self.logic.place_ship(self.dragging_ship_id, r, c, self.drag_orientation):
                        self.dragging_ship_id = None
                        self.check_ready_status()
                else:
                    self.dragging_ship_id = None
                    self.check_ready_status()
                self.update()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging_ship_id:
            self.update()
        else:
            super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Control and self.dragging_ship_id:
            self.drag_orientation = 'v' if self.drag_orientation == 'h' else 'h'
            self.update()
        super().keyPressEvent(event)

    def get_ship_at_dock(self, pos):
        start_x = 50
        base_y = self.dock_rect.y() + 30
        cs = self.cell_size
        for ship in self.logic.fleet_config:
            sid = ship["id"]
            if not self.logic.is_ship_placed(sid) and sid != self.dragging_ship_id:
                width = ship["size"] * cs
                if QRect(start_x, base_y, width, int(cs)).contains(pos): return sid
                start_x += width + 20
        return None

    def check_ready_status(self):
        if self.logic.are_all_placed():
            self.logic.phase = 'wait_ready'
            self.ready_btn.show()
            self.ready_btn.setEnabled(True)
        else:
            self.logic.phase = 'setup'
            self.ready_btn.hide()

    def on_ready_click(self):
        self.logic.phase = 'wait_opp'
        self.ready_btn.setText("ЖДЕМ СОПЕРНИКА...")
        self.ready_btn.setEnabled(False)
        self.update()

        if self.is_online and self.network:
            self.network.send_json({"type": "game_move", "sub_type": "battleship_ready"})

        if self.opponent_ready:
            self.start_game()

    def on_network_message(self, data):
        # 1. ГОТОВНОСТЬ
        if data.get("sub_type") == "battleship_ready":
            self.opponent_ready = True
            if self.logic.phase == 'wait_opp':
                self.start_game()

        # 2. СТРЕЛЬБА
        elif data.get("type") == "game_move":
            subtype = data.get("sub_type")

            if subtype == "shot":
                r, c = data["r"], data["c"]
                res, ship_data = self.logic.receive_shot(r, c)
                self.update()

                self.network.send_json({
                    "type": "game_move",
                    "sub_type": "shot_result",
                    "r": r, "c": c,
                    "status": res,
                    "ship_data": ship_data
                })

            elif subtype == "shot_result":
                r, c = data["r"], data["c"]
                status = data["status"]
                sdata = data.get("ship_data")
                self.logic.process_shot_result(r, c, status, sdata)
                self.update()

        if self.logic.game_over and not self.can_restart:
            # Запускаем таймер на 2 секунды
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, self.enable_restart)

    def enable_restart(self):
        self.can_restart = True

    def start_game(self):
        self.logic.phase = 'playing'
        self.ready_btn.hide()
        self.logic.my_turn = self.is_first_player
        self.update()

    def swap_sides(self, new_color):
        self.is_first_player = (new_color == 'white')

        # Сбрасываем логику
        self.logic.reset_game()

        # Сбрасываем UI (флаги, кнопки)
        self.opponent_ready = False
        self.dragging_ship_id = None
        self.drag_orientation = 'h'

        self.ready_btn.setText("Я ГОТОВ К БОЮ")
        self.ready_btn.hide()

        self.update()