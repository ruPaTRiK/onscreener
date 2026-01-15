import sys
import os
import json
import urllib.request
import threading
import ssl
from core.server_dialog import ServerSelectDialog

from core.updater import AutoUpdater
from core.update_dialog import UpdateProgressDialog

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QGridLayout, QScrollArea, QFrame,
                             QLineEdit, QStackedWidget, QListWidget, QListWidgetItem,
                             QCheckBox, QMessageBox)
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtCore import Qt, QTimer, QDateTime, pyqtSignal

from core.base_window import OverlayWindow
from core.network import NetworkClient
from core.coin_dialog import CoinFlipDialog
from core.lobby_dialogs import CreateLobbyDialog, PasswordDialog
from core.notifications import NotificationManager
from games_config import GAMES_CONFIG

from core.settings_panel import SettingsPanel
from core.settings import SettingsManager
from core.sound_manager import SoundManager


CURRENT_VERSION = "0.71"


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

        self.default_style = self._get_style("#3E3E50")
        self.selected_style = self._get_style("#2ed573")  # Зеленая рамка

        self.setStyleSheet(self.default_style)

        layout = QVBoxLayout(self)
        layout.addStretch()
        title = QLabel(game_data["title"])
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setStyleSheet("background-color: rgba(0,0,0,150); color: white; border-radius: 5px; border: none; padding: 5px 0;")
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
    servers_loaded = pyqtSignal(list)

    def __init__(self):
        super().__init__(overlay_mode=False)
        self.setWindowTitle("onscreener")
        self.setWindowFlags(Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.resize(1100, 750)

        self.notifications = NotificationManager(self)

        # Сеть
        self.network = NetworkClient()
        self.network.json_received.connect(self.on_server_data)
        self.network.data_sent.connect(self.on_client_data)
        self.network.connected.connect(self.on_connected)
        self.network.disconnected.connect(self.on_disconnected)
        self.network.error_occurred.connect(self.on_net_error)
        self.servers_loaded.connect(self.finish_loading_servers)

        self.user_name = "Player"
        self.my_id_in_lobby = None  # ID (1 или 2), который выдал сервер
        self.current_lobby_id = None
        self.is_host = False
        self.is_game_running = False
        self.active_game = None
        self.active_game_id = None
        self.game_cards = {}  # {game_id: card_widget}

        sm = SettingsManager()
        snd = SoundManager()
        snd.set_volume(sm.get("volume"))
        snd.muted = sm.get("mute")

        self.servers_list = []
        self.current_server_name = "Локальный"

        self.init_ui()

        # Автоподключение
        self.fetch_server_list_and_connect()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        scrollbar_style = """
                    /* ВЕРТИКАЛЬНЫЙ СКРОЛЛБАР */
                    QScrollBar:vertical {
                        border: none;
                        background: rgba(0, 0, 0, 30); /* Прозрачный темный фон трека */
                        width: 10px;                   /* Тонкий */
                        margin: 0px 0px 0px 0px;
                    }
                    /* Ползунок */
                    QScrollBar::handle:vertical {
                        background: rgba(255, 255, 255, 50); /* Полупрозрачный белый */
                        min-height: 20px;
                        border-radius: 5px;            /* Закругления */
                    }
                    /* Ползунок при наведении */
                    QScrollBar::handle:vertical:hover {
                        background: rgba(255, 255, 255, 100); /* Ярче */
                    }
                    /* Скрываем кнопки вверх/вниз */
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                        height: 0px;
                    }
                    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                        background: none;
                    }

                    /* ГОРИЗОНТАЛЬНЫЙ СКРОЛЛБАР */
                    QScrollBar:horizontal {
                        border: none;
                        background: rgba(0, 0, 0, 30);
                        height: 10px;
                        margin: 0px 0px 0px 0px;
                    }
                    QScrollBar::handle:horizontal {
                        background: rgba(255, 255, 255, 50);
                        min-width: 20px;
                        border-radius: 5px;
                    }
                    QScrollBar::handle:horizontal:hover {
                        background: rgba(255, 255, 255, 100);
                    }
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                        width: 0px;
                    }
                    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                        background: none;
                    }
                """
        self.setStyleSheet(scrollbar_style)

        self.main_h_layout = QHBoxLayout(self.central_widget)
        self.main_h_layout.setContentsMargins(0, 0, 0, 0)
        self.main_h_layout.setSpacing(0)

        self.settings_panel = SettingsPanel(self)
        self.settings_panel.opacity_changed.connect(self.update_game_opacity)

        # === ЛЕВАЯ ЧАСТЬ (ИГРЫ) ===
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel("Коллекция Игр")
        header.setObjectName("CollectionHeader")
        header.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        header.setStyleSheet("color: #EAEAEA;")
        self.left_layout.addWidget(header)

        btn_settings = QPushButton("⚙")
        btn_settings.clicked.connect(self.settings_panel.toggle)
        self.left_layout.addWidget(btn_settings)

        btn_srv = QPushButton("🌐")
        btn_srv.setFixedSize(40, 40)
        btn_srv.setToolTip("Сменить сервер")
        btn_srv.clicked.connect(self.open_server_dialog)
        btn_srv.setStyleSheet(
            "QPushButton { background: transparent; font-size: 20px; border: none; color: #aaa; } QPushButton:hover { color: white; }")

        self.left_layout.addWidget(btn_srv)

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
        line.setStyleSheet("color: #EAEAEA;")
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

        self.main_h_layout.addWidget(self.left_panel, stretch=3)

        # === ПРАВАЯ ЧАСТЬ (ОНЛАЙН) ===
        self.right_panel = QFrame()
        self.right_panel.setObjectName("RightPanel")
        self.right_panel.setStyleSheet("background-color: #2A2A3C; border: 10px solid #1E1E2E; border-radius: 25px;")
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(15, 20, 15, 20)

        lbl_online = QLabel("ОНЛАЙН ЛОББИ")
        lbl_online.setObjectName("OnlineHeader")
        lbl_online.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        lbl_online.setStyleSheet("color: #EAEAEA; border: none; background: transparent;")
        lbl_online.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_layout.addWidget(lbl_online)

        # Поле имени
        self.name_inp = QLineEdit("Player")
        self.name_inp.setPlaceholderText("Ваше имя")
        self.name_inp.setStyleSheet(
            "QLineEdit {padding: 5px; background: rgba(82, 97, 107, 20); color: #EAEAEA; border: none; border-radius: 7px;}"
            "QLineEdit:disabled {background-color: rgba(82, 97, 107, 50); color: #A0A0A0; border: none;}")
        self.name_inp.editingFinished.connect(self.update_name)
        self.right_layout.addWidget(self.name_inp)

        # Стек экранов
        self.stack = QStackedWidget()
        self.right_layout.addWidget(self.stack)
        self.stack.setStyleSheet("background: transparent; border: none;")

        # ЭКРАН 0: СПИСОК КОМНАТ
        self.page_list = QWidget()
        pl_layout = QVBoxLayout(self.page_list)
        pl_layout.setContentsMargins(0, 0, 0, 0)


        self.lobby_list_widget = QListWidget()
        self.lobby_list_widget.setStyleSheet("QListWidget {background: transparent; color: #EAEAEA; border: none;}"
                                             "QListWidget::item { background: rgba(82, 97, 107, 60); padding: 5px; margin: 5px 0; border-radius: 7px; color: #EAEAEA;}"
                                             "QListWidget::item:hover { background: rgba(82, 97, 107, 90); }"
                                             "QListWidget::item:selected { background: rgba(82, 97, 107, 70); }"
                                             "QListWidget::item:selected:active { background: rgba(82, 97, 107, 70); }")
        self.lobby_list_widget.itemDoubleClicked.connect(self.on_lobby_double_click)
        pl_layout.addWidget(self.lobby_list_widget)

        btn_create = QPushButton("Создать комнату")
        btn_create.setStyleSheet("background: #2ECC71; color: #EAEAEA; padding: 8px; border-radius: 7px;")
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
        self.room_players.setStyleSheet("QListWidget {background: transparent; color: #EAEAEA; border: none;}"
                                        "QListWidget::item { background: rgba(82, 97, 107, 60); padding: 5px; margin: 5px 0; border-radius: 7px; color: #EAEAEA;}"
                                        "QListWidget::item:hover { background: rgba(82, 97, 107, 90); }"
                                        "QListWidget::item:selected { background: rgba(82, 97, 107, 70); }"
                                        "QListWidget::item:selected:active { background: rgba(82, 97, 107, 70); }")
        pr_layout.addWidget(self.room_players)

        lbl_log = QLabel("Лог ходов:")
        lbl_log.setStyleSheet("color: #aaa; font-size: 12px; margin-top: 5px;")
        pr_layout.addWidget(lbl_log)

        self.room_log = QListWidget()
        self.room_log.setStyleSheet("background: rgba(0,0,0,50); border-radius: 5px; color: #ccc; font-size: 11px;")
        self.room_log.model().rowsInserted.connect(self.room_log.scrollToBottom)
        pr_layout.addWidget(self.room_log)

        self.lbl_selected_game = QLabel("Выберите игру слева")
        self.lbl_selected_game.setStyleSheet("color: #EAEAEA; background: transparent; border: none;")
        self.lbl_selected_game.setWordWrap(True)
        self.lbl_selected_game.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pr_layout.addWidget(self.lbl_selected_game)

        # Управление
        ctrl_layout = QHBoxLayout()
        self.check_ready = QCheckBox("Я ГОТОВ")
        self.check_ready.setStyleSheet("color: #EAEAEA; font-weight: bold;")
        self.check_ready.toggled.connect(self.send_ready_status)
        ctrl_layout.addWidget(self.check_ready)

        btn_leave = QPushButton("Выйти")
        btn_leave.setStyleSheet("background: #E74C3C; color: #EAEAEA; padding: 5px; border-radius: 5px;")
        btn_leave.clicked.connect(self.leave_lobby)
        ctrl_layout.addWidget(btn_leave)

        pr_layout.addLayout(ctrl_layout)
        self.stack.addWidget(self.page_room)

        self.main_h_layout.addWidget(self.right_panel, stretch=1)

        self.main_h_layout.addWidget(self.settings_panel)

    def load_games(self):
        r, c = 0, 0
        for game in GAMES_CONFIG:
            card = GameCard(game, self.on_game_click)
            self.grid_layout.addWidget(card, r, c)
            self.game_cards[game["id"]] = card
            c += 1
            if c > 2: c = 0; r += 1

    # --- СЕТЕВЫЕ СОБЫТИЯ ---
    def fetch_server_list_and_connect(self):
        def worker():
            try:
                url = "https://gist.githubusercontent.com/ruPaTRiK/fba2f42d20c7bb8893793928c3257880/raw/447c87e796460f816456de55d2235b5b7081d043/servers.json"

                req = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                )

                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE


                with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
                    text_data = response.read().decode('utf-8')
                    data = json.loads(text_data)

                    self.servers_loaded.emit(data)

            except Exception as e:
                self.servers_loaded.emit([])

        t = threading.Thread(target=self._thread_loader, args=(worker,))
        t.daemon = True
        t.start()

    def _thread_loader(self, worker):
        data = worker()
        # Возвращаемся в GUI поток
        QTimer.singleShot(0, lambda: self.finish_loading_servers(data))

    def run_update_thread(self, updater, url):
        # Callback для обновления прогресса из потока
        def progress_callback(percent):
            # QMetaObject.invokeMethod - безопасный способ обновить GUI из потока
            # Но проще через сигнал или QTimer
            QTimer.singleShot(0, lambda: self.update_dlg.set_progress(percent))

        success = updater.download_update(url, progress_callback)

        # Завершение
        QTimer.singleShot(0, lambda: self.finish_update(updater, success))

    def finish_update(self, updater, success):
        self.update_dlg.close()

        if success:
            self.notifications.show("Обновление", "Установка...", "success")
            # Даем секунду на отрисовку уведомления
            QTimer.singleShot(1000, updater.restart_and_replace)
        else:
            self.notifications.show("Ошибка", "Не удалось скачать обновление", "error")

    def finish_loading_servers(self, raw_data):
        servers = []

        if isinstance(raw_data, dict):
            remote_ver = raw_data.get("version", "0.0")
            download_url = raw_data.get("url", "")
            servers = raw_data.get("servers", [])

            # ПРОВЕРКА ОБНОВЛЕНИЯ
            updater = AutoUpdater(CURRENT_VERSION)
            if updater.is_update_available(remote_ver):
                reply = QMessageBox.question(
                    self, "Обновление",
                    f"Доступна новая версия {remote_ver}.\nОбновить сейчас?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    self.update_dlg = UpdateProgressDialog(self)
                    self.update_dlg.show()
                    t = threading.Thread(target=self.run_update_thread, args=(updater, download_url))
                    t.daemon = True
                    t.start()
                    return

        elif isinstance(raw_data, list):
            servers = raw_data

        self.servers_list = servers

        if self.servers_list:
            srv = self.servers_list[0]
            ip = srv['ip']
            port = srv.get('port', 5555)

            self.notifications.show("Сервер", f"Подключение к: {srv['name']}...", "info")
            self.network.connect_to(ip, port)
        else:
            self.network.connect_to("127.0.0.1", 5555)

    def open_server_dialog(self):
        dlg = ServerSelectDialog(self, self.servers_list)
        if dlg.exec():
            ip = dlg.result_ip
            port = dlg.result_port
            if ip:
                self.network.disconnect()  # Рвем старое

                self.notifications.show("Сервер", f"Переподключение к {ip}...", "info")
                # Небольшая задержка перед новым коннектом
                QTimer.singleShot(500, lambda: self.network.connect_to(ip, port))

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

            if self.active_game:
                self.active_game.close()
                self.active_game = None

            self.notifications.show("Игра", "Игра начинается!", "success")
            self.launch_online_game(data["game"], data["color"])

        elif dtype == "game_move" and self.active_game:
            if "data" in data:
                self.active_game.on_network_message(f"move:{data['data']}")
            else:
                # Если это сложный объект (Морской бой) - передаем весь словарь
                self.active_game.on_network_message(data)

            self.process_log_entry(data, "Соперник")

        elif dtype == "restart_cmd" and self.active_game:
            self.active_game.logic.reset_game()
            self.active_game._update_ui()
            self.notifications.show("Рестарт", "Игра перезапущена", "info")

        elif dtype == "restart_swap" and self.active_game:
            new_color = data["color"]
            # Вызываем метод смены сторон в игре
            if hasattr(self.active_game, "swap_sides"):
                self.active_game.swap_sides(new_color)
                self.notifications.show("Рестарт", "Смена сторон!", "success")

        elif dtype == "game_emote" and self.active_game:
            self.active_game.on_network_message(data)
            emoji = data.get("emoji")
            self.add_to_log(f"Соперник: {emoji}")

    def on_client_data(self, data):
        if data.get("type") == "game_move" and self.active_game:
            self.process_log_entry(data, "Вы")
        if data.get("type") == "game_emote":
            emoji = data.get("emoji")
            self.add_to_log(f"Вы: {emoji}")

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
        if self.current_lobby_id != data["lobby_id"]:
            self.room_log.clear()

        self.stack.setCurrentIndex(1)
        self.current_lobby_id = data["lobby_id"]
        self.is_host = data["am_i_host"]

        self.name_inp.setEnabled(False)

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
        self.name_inp.setEnabled(True)

    def send_ready_status(self, checked):
        self.network.send_json({"type": "toggle_ready", "status": checked})

    # --- КЛИКИ ПО ИГРАМ ---
    def on_game_click(self, game_data):
        if self.current_lobby_id and self.is_game_running:
            self.notifications.show("Игра идет", "Нельзя менять игру во время матча!", "warning")
            return

        # 1. Если не в лобби - Оффлайн запуск
        if not self.current_lobby_id:
            game_class = game_data["class"]
            win = game_class()
            win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            op = SettingsManager().get("window_opacity")
            win.setWindowOpacity(op)
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
            self.active_game_id = game_id

            if self.room_log.count() > 0:
                self.room_log.addItem(QListWidgetItem(""))
                self.room_log.addItem(QListWidgetItem("--- НОВАЯ ИГРА ---"))
                self.room_log.addItem(QListWidgetItem(""))

            game_class = game_conf["class"]
            # Внимание: is_host в игре значит "играю за белых".
            # Это совпадает с my_color, который прислал сервер
            play_as_white = (my_color == 'white')

            self.active_game = game_class(is_online=True, is_host=play_as_white, network_client=self.network)
            self.active_game.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            op = SettingsManager().get("window_opacity")
            self.active_game.setWindowOpacity(op)
            self.active_game.show()
            self.add_active_game_widget(self.active_game, f"{game_conf['title']} (Online)")

            self.is_game_running = True
            self.add_to_log(f"Игра {game_conf['title']} началась!")

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
            w.setParent(None)
            w.deleteLater()
            del self.running_games[window_id]

        self.is_game_running = False  # Разблокируем выбор игр

        if self.active_game and id(self.active_game) == window_id:
            self.active_game = None
            self.active_game_id = None

        # Если мы в лобби, снимаем готовность
        if self.current_lobby_id:
            self.check_ready.setChecked(False)  # Это автоматически отправит toggle_ready на сервер
            self.notifications.show("Лобби", "Игра завершена. Статус: Не готов", "info")
            self.add_to_log("Игра завершена")

    def add_to_log(self, message):
        import datetime
        time_str = QDateTime.currentDateTime().toString("HH:mm:ss")
        item = QListWidgetItem(f"[{time_str}] {message}")
        self.room_log.addItem(item)

    def format_coord(self, r, c, game_type):
        """Конвертирует (row, col) в строку для лога"""
        try:
            r, c = int(r), int(c)

            if game_type in ["chess", "checkers"]:
                # Шахматы/Шашки: A1..H8
                letters = "ABCDEFGH"
                return f"{letters[c]}{8 - r}"

            elif game_type == "tic_tac_toe":
                # Крестики: Ряд 1..3, Стлб 1..3
                return f"Ряд {r + 1}, Стлб {c + 1}"

            elif game_type == "battleship":
                # Морской бой: А1..К10
                letters = "АБВГДЕЖЗИК"
                return f"{letters[c]}{r + 1}"

            return f"({r}, {c})"
        except:
            return "??"

    def process_log_entry(self, data, source):
        """
        data: JSON с ходом
        source: 'Вы' или 'Соперник'
        """
        if not self.active_game_id: return

        # --- ШАШКИ И ШАХМАТЫ ---
        if self.active_game_id in ["chess", "checkers"]:
            if "data" in data and ":" in data["data"]:
                try:
                    # data="r1,c1:r2,c2"
                    start, end = data["data"].split(":")
                    r1, c1 = start.split(",")
                    r2, c2 = end.split(",")

                    p1 = self.format_coord(r1, c1, self.active_game_id)
                    p2 = self.format_coord(r2, c2, self.active_game_id)
                    self.add_to_log(f"{source}: {p1} -> {p2}")
                except:
                    pass

        # --- КРЕСТИКИ-НОЛИКИ ---
        elif self.active_game_id == "tic_tac_toe":
            if "data" in data:
                try:
                    r, c = data["data"].split(",")
                    pos = self.format_coord(r, c, self.active_game_id)
                    self.add_to_log(f"{source}: {pos}")
                except:
                    pass

        # --- МОРСКОЙ БОЙ ---
        elif self.active_game_id == "battleship":
            subtype = data.get("sub_type")
            if subtype == "shot":
                r, c = data.get("r"), data.get("c")
                pos = self.format_coord(r, c, self.active_game_id)
                action = "стреляет в" if source == "Соперник" else "выстрел в"
                self.add_to_log(f"{source}: {action} {pos}")

            elif subtype == "shot_result":
                # Результат логируем, только если это ответ на НАШ выстрел (или наоборот, по желанию)
                status = data.get("status")
                # Для красоты переведем статусы
                status_map = {"hit": "ПОПАДАНИЕ", "miss": "ПРОМАХ", "kill": "УБИЛ"}
                ru_status = status_map.get(status, status)

                # Если source="Соперник", значит это он прислал результат своего попадания?
                # Нет, shot_result посылает тот, в кого стреляли.
                # Если data пришла от сервера -> Соперник сообщает результат МОЕГО выстрела.
                # Если data отправлена мной -> Я сообщаю результат ЕГО выстрела.

                if source == "Соперник":
                    self.add_to_log(f"Результат вашего выстрела: {ru_status}")
                else:
                    self.add_to_log(f"Результат выстрела соперника: {ru_status}")

    def paintEvent(self, event):
        self.central_widget.setStyleSheet("background-color: #1E1E2E;")
        super().paintEvent(event)

    def resizeEvent(self, event):
        self.notifications.reposition_toasts()
        super().resizeEvent(event)

    def update_game_opacity(self, opacity):
        if self.active_game:
            self.active_game.setWindowOpacity(opacity)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    l = Launcher()
    l.show()
    sys.exit(app.exec())