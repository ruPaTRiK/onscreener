import sys
import os
import json
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QGridLayout, QScrollArea, QFrame,
                             QLineEdit, QStackedWidget, QListWidget, QListWidgetItem,
                             QCheckBox, QMessageBox)
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtCore import Qt, QTimer

from core.base_window import OverlayWindow
from core.network import NetworkClient
from core.coin_dialog import CoinFlipDialog
from core.lobby_dialogs import CreateLobbyDialog, PasswordDialog
from core.notifications import NotificationManager
from games_config import GAMES_CONFIG


# --- ВИДЖЕТ АКТИВНОЙ ИГРЫ (Снизу слева) ---
class ActiveGameItem(QFrame):
    def __init__(self, title, on_close_click):
        super().__init__()
        self.setFixedHeight(50)
        self.setStyleSheet("background-color: rgba(255, 255, 255, 20); border-radius: 10px;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        name_lbl = QLabel(title)
        name_lbl.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        layout.addWidget(name_lbl)
        layout.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background-color: #e74c3c; color: white; border-radius: 15px; border: none; font-weight: bold; } QPushButton:hover { background-color: #c0392b; }")
        close_btn.clicked.connect(on_close_click)
        layout.addWidget(close_btn)


# --- КАРТОЧКА ИГРЫ ---
class GameCard(QFrame):
    def __init__(self, game_data, on_click_callback):
        super().__init__()
        self.game_data = game_data
        self.on_click_callback = on_click_callback
        self.setFixedSize(180, 100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_selected = False

        self.default_style = self._get_style("#444")
        self.selected_style = self._get_style("#2ecc71")  # Зеленая рамка

        self.setStyleSheet(self.default_style)

        layout = QVBoxLayout(self)
        layout.addStretch()
        title = QLabel(game_data["title"])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setStyleSheet("background-color: rgba(0,0,0,150); color: white; border-radius: 5px;")
        layout.addWidget(title)

    def _get_style(self, border_color):
        bg = ""
        if os.path.exists(self.game_data["image"]):
            path = self.game_data["image"].replace("\\", "/")
            bg = f"border-image: url({path}) 0 0 0 0 stretch;"
        else:
            bg = f"background-color: {self.game_data.get('color', '#555')};"
        return f"QFrame {{ {bg} border-radius: 10px; border: 3px solid {border_color}; }}"

    def set_selected(self, selected):
        self.is_selected = selected
        self.setStyleSheet(self.selected_style if selected else self.default_style)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_click_callback(self.game_data)


# --- ЛАУНЧЕР ---
class Launcher(OverlayWindow):
    def __init__(self):
        super().__init__(overlay_mode=False)
        self.resize(1100, 750)

        self.notifications = NotificationManager(self)

        # Сеть
        self.network = NetworkClient()
        self.network.json_received.connect(self.on_server_data)
        self.network.connected.connect(self.on_connected)
        self.network.disconnected.connect(self.on_disconnected)
        self.network.error_occurred.connect(self.on_net_error)

        self.user_name = "Player"
        self.my_id_in_lobby = None  # ID (1 или 2), который выдал сервер
        self.current_lobby_id = None
        self.is_host = False
        self.game_cards = {}  # {game_id: card_widget}

        self.init_ui()

        # Автоподключение
        QTimer.singleShot(500, self.network.connect_auto)

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_h_layout = QHBoxLayout(self.central_widget)
        self.main_h_layout.setContentsMargins(0, 0, 0, 0)
        self.main_h_layout.setSpacing(0)

        # === ЛЕВАЯ ЧАСТЬ (ИГРЫ) ===
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel("Коллекция Игр")
        header.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        self.left_layout.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.grid_cont = QWidget()
        self.grid_layout = QGridLayout(self.grid_cont)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.grid_cont)
        self.left_layout.addWidget(self.scroll)

        self.load_games()

        # Нижняя часть левой панели (Активные игры + Выход)
        self.left_layout.addStretch()

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: rgba(255,255,255,50);")
        self.left_layout.addWidget(line)

        self.active_games_container = QWidget()
        self.active_games_layout = QVBoxLayout(self.active_games_container)
        self.active_games_layout.setContentsMargins(0, 0, 0, 0)
        self.active_scroll = QScrollArea()
        self.active_scroll.setFixedHeight(100)
        self.active_scroll.setWidgetResizable(True)
        self.active_scroll.setStyleSheet("background: transparent; border: none;")
        self.active_scroll.setWidget(self.active_games_container)
        self.left_layout.addWidget(self.active_scroll)

        btn_exit = QPushButton("Закрыть программу")
        btn_exit.setStyleSheet("color: #aaa; background: transparent; font-size: 14px; text-align: left;")
        btn_exit.clicked.connect(self.close)
        self.left_layout.addWidget(btn_exit)

        self.main_h_layout.addWidget(self.left_panel, stretch=3)

        # === ПРАВАЯ ЧАСТЬ (ОНЛАЙН) ===
        self.right_panel = QFrame()
        self.right_panel.setStyleSheet("background-color: rgba(0, 0, 0, 80); border-left: 1px solid #555;")
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(15, 20, 15, 20)

        lbl_online = QLabel("ОНЛАЙН ЛОББИ")
        lbl_online.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        lbl_online.setStyleSheet("color: white; border: none; background: transparent;")
        lbl_online.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_layout.addWidget(lbl_online)

        # Поле имени
        self.name_inp = QLineEdit("Player")
        self.name_inp.setPlaceholderText("Ваше имя")
        self.name_inp.setStyleSheet(
            "padding: 5px; background: rgba(255,255,255,30); color: white; border: 1px solid #777; border-radius: 5px;")
        self.name_inp.editingFinished.connect(self.update_name)
        self.right_layout.addWidget(self.name_inp)

        # Стек экранов
        self.stack = QStackedWidget()
        self.right_layout.addWidget(self.stack)

        # ЭКРАН 0: СПИСОК КОМНАТ
        self.page_list = QWidget()
        pl_layout = QVBoxLayout(self.page_list)
        pl_layout.setContentsMargins(0, 0, 0, 0)

        self.lobby_list_widget = QListWidget()
        self.lobby_list_widget.setStyleSheet("background: transparent; color: white; border: none;")
        self.lobby_list_widget.itemDoubleClicked.connect(self.on_lobby_double_click)
        pl_layout.addWidget(self.lobby_list_widget)

        btn_create = QPushButton("Создать комнату")
        btn_create.setStyleSheet("background: #27ae60; color: white; padding: 8px; border-radius: 5px;")
        btn_create.clicked.connect(self.open_create_dialog)
        pl_layout.addWidget(btn_create)

        self.stack.addWidget(self.page_list)

        # ЭКРАН 1: ВНУТРИ ЛОББИ
        self.page_room = QWidget()
        pr_layout = QVBoxLayout(self.page_room)

        self.room_title = QLabel("Комната")
        self.room_title.setStyleSheet(
            "color: gold; font-size: 16px; font-weight: bold; background: transparent; border: none;")
        self.room_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pr_layout.addWidget(self.room_title)

        self.room_players = QListWidget()
        self.room_players.setStyleSheet("background: rgba(0,0,0,50); color: white; border-radius: 5px;")
        pr_layout.addWidget(self.room_players)

        self.lbl_selected_game = QLabel("Выберите игру слева")
        self.lbl_selected_game.setStyleSheet("color: #aaa; background: transparent; border: none;")
        self.lbl_selected_game.setWordWrap(True)
        self.lbl_selected_game.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pr_layout.addWidget(self.lbl_selected_game)

        # Управление
        ctrl_layout = QHBoxLayout()
        self.check_ready = QCheckBox("Я ГОТОВ")
        self.check_ready.setStyleSheet("color: white; font-weight: bold;")
        self.check_ready.toggled.connect(self.send_ready_status)
        ctrl_layout.addWidget(self.check_ready)

        btn_leave = QPushButton("Выйти")
        btn_leave.setStyleSheet("background: #c0392b; color: white; padding: 5px; border-radius: 5px;")
        btn_leave.clicked.connect(self.leave_lobby)
        ctrl_layout.addWidget(btn_leave)

        pr_layout.addLayout(ctrl_layout)
        self.stack.addWidget(self.page_room)

        self.main_h_layout.addWidget(self.right_panel, stretch=1)

    def load_games(self):
        r, c = 0, 0
        for game in GAMES_CONFIG:
            card = GameCard(game, self.on_game_click)
            self.grid_layout.addWidget(card, r, c)
            self.game_cards[game["id"]] = card
            c += 1
            if c > 2: c = 0; r += 1

    # --- СЕТЕВЫЕ СОБЫТИЯ ---
    def on_connected(self):
        self.network.send_json({"type": "login", "name": self.name_inp.text()})
        self.notifications.show("Сервер", "Подключено успешно!", "success")

    def on_disconnected(self):
        self.notifications.show("Сервер", "Соединение разорвано", "error")
        self.stack.setCurrentIndex(0)
        self.lobby_list_widget.clear()

    def on_net_error(self, err):
        pass  # Можно логировать

    def on_server_data(self, data):
        dtype = data.get("type")

        if dtype == "lobby_list":
            self.update_lobby_list(data["lobbies"])

        elif dtype == "lobby_state":
            self.update_room_ui(data)

        elif dtype == "kicked":
            self.notifications.show("Лобби", data["msg"], "warning")
            self.stack.setCurrentIndex(0)
            self.current_lobby_id = None
            self.deselect_all_games()

        elif dtype == "error":
            self.notifications.show("Ошибка", data["msg"], "error")

        elif dtype == "left_lobby_success":
            self.stack.setCurrentIndex(0)
            self.current_lobby_id = None
            self.deselect_all_games()

        # ЗАПУСК ИГРЫ
        elif dtype == "match_found":
            role = data["role"]
            self.coin_dialog = CoinFlipDialog(self, "pick" if role == "picker" else "wait")
            if role == "picker":
                self.coin_dialog.choice_made.connect(
                    lambda c: self.network.send_json({"type": "coin_choice", "choice": c}))
            self.coin_dialog.show()

        elif dtype == "coin_result":
            if self.coin_dialog:
                self.coin_dialog.start_animation(data["result"], data["win"])
                if data["win"]:
                    self.coin_dialog.order_made.connect(
                        lambda o: self.network.send_json({"type": "order_choice", "choice": o}))

        elif dtype == "start_game":
            if self.coin_dialog: self.coin_dialog.accept()
            self.notifications.show("Игра", "Игра начинается!", "success")
            self.launch_online_game(data["game"], data["color"])

        elif dtype == "game_move" and self.active_game:
            if "data" in data:
                self.active_game.on_network_message(f"move:{data['data']}")
            else:
                # Если это сложный объект (Морской бой) - передаем весь словарь
                self.active_game.on_network_message(data)

        elif dtype == "restart_cmd" and self.active_game:
            self.active_game.logic.reset_game()
            self.active_game._update_ui()
            self.notifications.show("Рестарт", "Игра перезапущена", "info")

    def update_name(self):
        if self.network.is_running:
            self.network.send_json({"type": "login", "name": self.name_inp.text()})

    # --- ЛОГИКА СПИСКА ЛОББИ ---
    def update_lobby_list(self, lobbies):
        self.lobby_list_widget.clear()
        for l in lobbies:
            lock = "🔒 " if l["private"] else ""
            text = f"{lock}{l['name']} ({l['players']}/{l['max']})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, l["id"])  # Храним ID внутри
            item.setData(Qt.ItemDataRole.UserRole + 1, l["private"])
            self.lobby_list_widget.addItem(item)

    def on_lobby_double_click(self, item):
        lid = item.data(Qt.ItemDataRole.UserRole)
        is_private = item.data(Qt.ItemDataRole.UserRole + 1)
        pwd = ""

        if is_private:
            dlg = PasswordDialog(self)
            if dlg.exec():
                pwd = dlg.get_password()
            else:
                return  # Отмена

        self.network.send_json({"type": "join_lobby", "lobby_id": lid, "password": pwd})

    def open_create_dialog(self):
        dlg = CreateLobbyDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            self.network.send_json({"type": "create_lobby", **data})

    # --- ЛОГИКА ВНУТРИ КОМНАТЫ ---
    def update_room_ui(self, data):
        self.stack.setCurrentIndex(1)
        self.current_lobby_id = data["lobby_id"]
        self.is_host = data["am_i_host"]

        self.room_title.setText(f"Комната: {data['name']}")

        self.room_players.clear()
        for p in data["players"]:
            status = "✅ Готов" if p["ready"] else "⏳ Не готов"
            host_mark = "👑 " if p["is_host"] else ""
            text = f"{host_mark}{p['name']} - {status}"
            self.room_players.addItem(text)

            # Если это я, обновляем галочку (на всякий случай)
            # if p["name"] == self.name_inp.text():
            #     self.check_ready.blockSignals(True)
            #     self.check_ready.setChecked(p["ready"])
            #     self.check_ready.blockSignals(False)

        # Выбор игры
        sel_game = data["selected_game"]
        if sel_game:
            # Подсвечиваем
            self.deselect_all_games()
            if sel_game in self.game_cards:
                self.game_cards[sel_game].set_selected(True)
                title = GAMES_CONFIG[0]["title"]  # (ищем по id, тут упрощено)
                for g in GAMES_CONFIG:
                    if g["id"] == sel_game: title = g["title"]
                self.lbl_selected_game.setText(f"Выбрана: {title}")
                self.lbl_selected_game.setStyleSheet(
                    "color: #2ecc71; font-weight: bold; background: transparent; border: none;")
        else:
            self.deselect_all_games()
            self.lbl_selected_game.setText("Хост выбирает игру...")
            self.lbl_selected_game.setStyleSheet("color: #aaa; background: transparent; border: none;")

        # Управление доступностью
        self.check_ready.setEnabled(True)
        # Если игра не выбрана - нельзя быть готовым
        if not sel_game:
            self.check_ready.setChecked(False)
            self.check_ready.setEnabled(False)

    def leave_lobby(self):
        self.network.send_json({"type": "leave_lobby"})
        self.check_ready.setChecked(False)

    def send_ready_status(self, checked):
        self.network.send_json({"type": "toggle_ready", "status": checked})

    # --- КЛИКИ ПО ИГРАМ ---
    def on_game_click(self, game_data):
        # 1. Если не в лобби - Оффлайн запуск
        if not self.current_lobby_id:
            game_class = game_data["class"]
            win = game_class()
            win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            win.show()
            self.add_active_game_widget(win, game_data["title"])
            return

        # 2. Если в лобби
        if self.is_host:
            # Хост выбирает игру для всех
            self.network.send_json({"type": "select_game", "game_id": game_data["id"]})
        else:
            # Гость не может выбирать
            self.notifications.show("Внимание", "Только хост может выбирать игру", "warning")

    def deselect_all_games(self):
        for card in self.game_cards.values():
            card.set_selected(False)

    def launch_online_game(self, game_id, my_color):
        game_conf = next((g for g in GAMES_CONFIG if g["id"] == game_id), None)
        if game_conf:
            game_class = game_conf["class"]
            # Внимание: is_host в игре значит "играю за белых".
            # Это совпадает с my_color, который прислал сервер
            play_as_white = (my_color == 'white')

            self.active_game = game_class(is_online=True, is_host=play_as_white, network_client=self.network)
            self.active_game.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self.active_game.show()
            self.add_active_game_widget(self.active_game, f"{game_conf['title']} (Online)")

    # --- СПИСОК ЗАПУЩЕННЫХ ---
    def add_active_game_widget(self, game_window, title):
        if not hasattr(self, 'running_games'): self.running_games = {}
        item = ActiveGameItem(title, lambda: game_window.close())
        self.active_games_layout.addWidget(item)
        self.running_games[id(game_window)] = item
        game_window.destroyed.connect(lambda: self.remove_active_game_widget(id(game_window)))

    def remove_active_game_widget(self, window_id):
        if hasattr(self, 'running_games') and window_id in self.running_games:
            w = self.running_games[window_id]
            w.setParent(None);
            w.deleteLater()
            del self.running_games[window_id]

    def paintEvent(self, event):
        self.central_widget.setStyleSheet("background-color: rgba(30, 30, 30, 245); border-radius: 15px;")
        super().paintEvent(event)

    def resizeEvent(self, event):
        self.notifications.reposition_toasts()
        super().resizeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    l = Launcher()
    l.show()
    sys.exit(app.exec())