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
                             QCheckBox, QMessageBox, QButtonGroup, QGraphicsOpacityEffect,
                             QGraphicsDropShadowEffect)
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtCore import Qt, QTimer, QDateTime, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint

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
class GameCard(QWidget):  # Внешний контейнер - QWidget (прозрачный)
    def __init__(self, game_data, on_click_callback):
        super().__init__()
        self.game_data = game_data
        self.on_click_callback = on_click_callback

        # Размер карточки + запас под тень (по 10px с каждой стороны)
        self.setFixedSize(240, 160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # ВНУТРЕННИЙ ФРЕЙМ (Сама карточка)
        self.card = QFrame(self)
        self.card.setGeometry(10, 10, 220, 140)  # Отступ 10px

        # Стиль для внутренней карточки
        # Сохраняем стиль в переменную, чтобы восстанавливать при leaveEvent
        self.default_style = """
            QFrame {
                background-color: #1a1a3a;
                border: 1px solid #2a2a4a;
                border-radius: 15px;
            }
        """
        self.hover_style = """
            QFrame {
                background-color: #202040;
                border: 1px solid #6366f1;
                border-radius: 15px;
            }
        """
        self.card.setStyleSheet(self.default_style)

        # ЛЭЙАУТ ВНУТРИ КАРТОЧКИ
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Картинка
        img_path = game_data.get("image", "")
        bg_image = ""
        if os.path.exists(img_path):
            img_path = img_path.replace("\\", "/")
            bg_image = f"border-image: url({img_path}) 0 0 0 0 stretch;"
        else:
            bg_image = "background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #555, stop:1 #333);"

        self.image_lbl = QLabel()
        self.image_lbl.setStyleSheet(f"""
            QLabel {{
                {bg_image}
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
            }}
        """)
        layout.addWidget(self.image_lbl, stretch=1)

        # Текст
        title_lbl = QLabel(game_data["title"])
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: white; padding: 8px; background: transparent; border: none;")
        layout.addWidget(title_lbl)

        # ЭФФЕКТ ТЕНИ (Теперь безопасно)
        self.shadow = QGraphicsDropShadowEffect(self.card)
        self.shadow.setBlurRadius(15)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(5)
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.card.setGraphicsEffect(self.shadow)

        # Анимация позиции (для всплытия)
        self.anim_pos = QPropertyAnimation(self.card, b"pos")
        self.anim_pos.setDuration(200)
        self.anim_pos.setEasingCurve(QEasingCurve.Type.OutQuad)

    def enterEvent(self, event):
        # 1. Меняем стиль (цвет рамки)
        self.card.setStyleSheet(self.hover_style)

        # 2. Цвет тени (Свечение)
        self.shadow.setColor(QColor(99, 102, 241, 150))  # Индиго
        self.shadow.setBlurRadius(30)

        # 3. Поднимаем карточку (уменьшаем Y на 5px)
        self.anim_pos.stop()
        self.anim_pos.setStartValue(self.card.pos())
        self.anim_pos.setEndValue(QPoint(10, 5))  # Было 10, стало 5 (вверх)
        self.anim_pos.start()

    def leaveEvent(self, event):
        # Возврат
        self.card.setStyleSheet(self.default_style)
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.shadow.setBlurRadius(15)

        self.anim_pos.stop()
        self.anim_pos.setStartValue(self.card.pos())
        self.anim_pos.setEndValue(QPoint(10, 10))  # Обратно вниз
        self.anim_pos.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_click_callback(self.game_data)


# --- ЛАУНЧЕР ---
class Launcher(OverlayWindow):
    servers_loaded = pyqtSignal(object)

    update_progress_signal = pyqtSignal(int)
    update_finished_signal = pyqtSignal(bool)

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
        self.update_progress_signal.connect(self.on_update_progress)
        self.update_finished_signal.connect(self.finish_update)

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
        self.central_widget.setObjectName("CentralWidget")
        self.central_widget.setStyleSheet("background-color: #0d0d1a;")
        self.setCentralWidget(self.central_widget)

        # ГЛАВНЫЙ ГОРИЗОНТАЛЬНЫЙ СЛОЙ (Сайдбар | Контент)
        self.root_layout = QHBoxLayout(self.central_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # === 1. ЛЕВАЯ НАВИГАЦИЯ (САЙДБАР) ===
        self.setup_sidebar()
        self.root_layout.addWidget(self.sidebar_frame)

        # === 2. ОБЛАСТЬ КОНТЕНТА ===
        self.main_stack = QStackedWidget()
        self.root_layout.addWidget(self.main_stack)

        # --- СТРАНИЦА 1: ИГРЫ ---
        self.page_games = QWidget()
        self.page_games.setStyleSheet("background: transparent;")

        self.game_page_layout = QHBoxLayout(self.page_games)
        self.game_page_layout.setContentsMargins(0, 0, 0, 0)
        self.game_page_layout.setSpacing(0)

        self.create_games_panel()
        self.game_page_layout.addWidget(self.games_panel_widget, stretch=3)
        self.create_online_panel()
        self.game_page_layout.addWidget(self.online_panel_widget, stretch=1)

        self.main_stack.addWidget(self.page_games)

        # --- СТРАНИЦА 2: ДРУЗЬЯ ---
        self.page_friends = QLabel("Раздел Друзья (В разработке)")
        self.page_friends.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_friends.setStyleSheet("color: #6b7280; font-size: 24px;")
        self.main_stack.addWidget(self.page_friends)

        # --- СТРАНИЦА 3: НАСТРОЙКИ ---
        self.page_settings = QLabel("Раздел Настройки")
        self.page_settings.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_settings.setStyleSheet("color: #6b7280; font-size: 24px;")
        self.main_stack.addWidget(self.page_settings)

    def setup_sidebar(self):
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setFixedWidth(70)  # w-16 ~ 64px, сделаем чуть шире для удобства
        self.sidebar_frame.setObjectName("Sidebar")

        # Стили (перевод твоего Tailwind в CSS)
        self.sidebar_frame.setStyleSheet("""
            QFrame#Sidebar {
                background-color: #12122a; 
                border-right: 1px solid #2a2a4a;
            }
            /* Кнопки навигации */
            QPushButton {
                border: none;
                border-radius: 12px; /* rounded-xl */
                background-color: transparent;
                color: #6b7280; /* text-gray-500 */
                font-size: 24px; /* Размер иконки */
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #1a1a3a;
                color: #e5e7eb;
            }
            /* Активная кнопка (checked) */
            QPushButton:checked {
                background-color: rgba(99, 102, 241, 0.2); /* bg-indigo-500/20 */
                color: #818cf8; /* text-indigo-400 */
            }

            /* Логотип */
            QLabel#Logo {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #6366f1, stop:1 #9333ea);
                border-radius: 12px;
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
        """)

        layout = QVBoxLayout(self.sidebar_frame)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(20)

        # 1. Логотип (Градиентный квадрат)
        lbl_logo = QLabel("G")
        lbl_logo.setObjectName("Logo")
        lbl_logo.setFixedSize(40, 40)
        lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_logo, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(20)  # Отступ mb-8

        # 2. Навигация
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        # Кнопка ИГРЫ
        self.btn_nav_games = QPushButton("🎮")  # Или иконка
        self.btn_nav_games.setFixedSize(40, 40)
        self.btn_nav_games.setCheckable(True)
        self.btn_nav_games.setChecked(True)  # Активна по умолчанию
        self.btn_nav_games.setToolTip("Игры")
        self.btn_nav_games.clicked.connect(lambda: self.main_stack.setCurrentIndex(0))
        self.nav_group.addButton(self.btn_nav_games)
        layout.addWidget(self.btn_nav_games, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Кнопка ДРУЗЬЯ
        self.btn_nav_friends = QPushButton("👥")
        self.btn_nav_friends.setFixedSize(40, 40)
        self.btn_nav_friends.setCheckable(True)
        self.btn_nav_friends.setToolTip("Друзья")
        self.btn_nav_friends.clicked.connect(lambda: self.main_stack.setCurrentIndex(1))
        self.nav_group.addButton(self.btn_nav_friends)
        layout.addWidget(self.btn_nav_friends, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Кнопка НАСТРОЙКИ
        self.btn_nav_settings = QPushButton("⚙")
        self.btn_nav_settings.setFixedSize(40, 40)
        self.btn_nav_settings.setCheckable(True)
        self.btn_nav_settings.setToolTip("Настройки")
        self.btn_nav_settings.clicked.connect(lambda: self.main_stack.setCurrentIndex(2))
        self.nav_group.addButton(self.btn_nav_settings)
        layout.addWidget(self.btn_nav_settings, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()  # Прижать все наверх

    def create_games_panel(self):
        self.games_panel_widget = QWidget()
        # Основной вертикальный слой
        layout = QVBoxLayout(self.games_panel_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # === 1. HEADER (Поиск и Заголовок) ===
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: rgba(13, 13, 26, 0.9); /* #0d0d1a/90 */
                border-bottom: 1px solid #2a2a4a;
            }
        """)
        header.setFixedHeight(80)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(30, 0, 30, 0)

        # Заголовок
        lbl_title = QLabel("Коллекция")
        lbl_title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: white; background: transparent; border: none;")
        h_layout.addWidget(lbl_title)

        h_layout.addStretch()

        # Поиск
        search_inp = QLineEdit()
        search_inp.setPlaceholderText("Поиск игр...")
        search_inp.setFixedWidth(250)
        search_inp.setStyleSheet("""
            QLineEdit {
                background-color: #1a1a3a;
                color: white;
                border: 1px solid #2a2a4a;
                border-radius: 12px;
                padding: 8px 15px;
                font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #6366f1; }
        """)
        h_layout.addWidget(search_inp)

        layout.addWidget(header)

        # === 2. SCROLL AREA С ИГРАМИ ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: #0d0d1a;")  # Фон контента

        self.grid_layout = QGridLayout(scroll_content)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.grid_layout.setContentsMargins(30, 30, 30, 80)  # pb-20 (отступ снизу)
        self.grid_layout.setSpacing(25)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Загрузка карточек
        self.load_games()

        # === 3. НИЖНИЙ STATUS BAR (Прижат к низу) ===
        self.status_bar = QFrame()
        self.status_bar.setFixedHeight(80)
        self.status_bar.setStyleSheet("""
            QFrame {
                background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #1a1a3a, stop:1 #12122a);
                border-top: 1px solid #2a2a4a;
            }
        """)
        sb_layout = QHBoxLayout(self.status_bar)
        sb_layout.setContentsMargins(30, 0, 30, 0)

        # Левая часть: Индикатор статуса
        # Используем StackedWidget, чтобы менять "Idle" и "Running"
        self.status_stack = QStackedWidget()
        self.status_stack.setStyleSheet("background: transparent; border: none;")
        self.status_stack.setFixedSize(300, 60)

        # Состояние IDLE (Ничего не запущено)
        page_idle = QWidget()
        pi_layout = QHBoxLayout(page_idle)
        pi_layout.setContentsMargins(0, 0, 0, 0)
        dot_idle = QLabel()
        dot_idle.setFixedSize(12, 12)
        dot_idle.setStyleSheet("background-color: #4b5563; border-radius: 6px;")  # gray-600
        lbl_idle = QLabel("Нет запущенных игр")
        lbl_idle.setStyleSheet("color: #6b7280; font-weight: 500; font-size: 14px; border: none;")
        pi_layout.addWidget(dot_idle)
        pi_layout.addWidget(lbl_idle)
        pi_layout.addStretch()
        self.status_stack.addWidget(page_idle)

        # Состояние RUNNING (Игра идет)
        page_run = QWidget()
        pr_layout = QHBoxLayout(page_run)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        dot_run = QLabel()
        dot_run.setFixedSize(12, 12)
        dot_run.setStyleSheet(
            "background-color: #34d399; border-radius: 6px; border: 2px solid rgba(52, 211, 153, 0.5);")  # emerald

        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        lbl_status = QLabel("ИГРА ЗАПУЩЕНА")
        lbl_status.setStyleSheet("color: #6b7280; font-size: 10px; font-weight: bold; border: none;")
        self.lbl_running_name = QLabel("Название игры")
        self.lbl_running_name.setStyleSheet("color: white; font-size: 16px; font-weight: bold; border: none;")
        text_layout.addWidget(lbl_status)
        text_layout.addWidget(self.lbl_running_name)

        pr_layout.addWidget(dot_run)
        pr_layout.addLayout(text_layout)
        pr_layout.addStretch()
        self.status_stack.addWidget(page_run)

        sb_layout.addWidget(self.status_stack)
        sb_layout.addStretch()

        # Правая часть: Кнопка закрыть
        self.btn_stop_game = QPushButton("Закрыть игру")
        self.btn_stop_game.setFixedSize(140, 40)
        self.btn_stop_game.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop_game.clicked.connect(self.close_active_game)  # Создадим этот метод
        self.btn_stop_game.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.1); /* red-500/10 */
                color: #fca5a5; /* red-300 */
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.2);
                color: #fecaca; /* red-200 */
            }
        """)
        self.btn_stop_game.hide()  # Скрыта по умолчанию
        sb_layout.addWidget(self.btn_stop_game)

        layout.addWidget(self.status_bar)

    def create_online_panel(self):
        self.online_panel_widget = QFrame()
        self.online_panel_widget.setFixedWidth(320)
        self.online_panel_widget.setObjectName("NetworkPanel")

        # Стили (Tailwind-like)
        self.online_panel_widget.setStyleSheet("""
                    QFrame#NetworkPanel {
                        background-color: #12122a; /* bg-[#12122a] */
                        border-left: 1px solid #2a2a4a;
                    }
                """)

        main_layout = QVBoxLayout(self.online_panel_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === HEADER ПАНЕЛИ ===
        header = QFrame()
        header.setStyleSheet("""
                    QFrame {
                        background-color: #12122a;
                        border-bottom: 1px solid #2a2a4a;
                    }
                """)
        header.setFixedHeight(70)  # p-6 (24px) ~ 70-80px
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)

        # Иконка (текстом 🌍) и Заголовок
        title_box = QHBoxLayout()
        title_box.setSpacing(10)

        icon_lbl = QLabel("🌍")  # Заглушка SVG
        icon_lbl.setStyleSheet("font-size: 18px; color: #818cf8;")  # indigo-400

        title_lbl = QLabel("Мультиплеер")
        title_lbl.setFont(QFont("Arial", 12, QFont.Weight.Bold))  # text-lg font-bold
        title_lbl.setStyleSheet("color: white; border: none;")

        title_box.addWidget(icon_lbl)
        title_box.addWidget(title_lbl)
        h_layout.addLayout(title_box)

        h_layout.addStretch()

        # Индикатор (Красная точка)
        self.conn_indicator = QLabel()
        self.conn_indicator.setFixedSize(10, 10)
        # Стиль для "Не подключено" (red-500 + shadow)
        self.style_disconnected = """
                    background-color: #ef4444; 
                    border-radius: 5px;
                    border: 1px solid #b91c1c;
                """
        # Стиль для "Подключено" (green-500 + shadow)
        self.style_connected = """
                    background-color: #22c55e;
                    border-radius: 5px;
                    border: 1px solid #15803d;
                """
        self.conn_indicator.setStyleSheet(self.style_disconnected)
        self.conn_indicator.setToolTip("Не подключено")
        h_layout.addWidget(self.conn_indicator)

        main_layout.addWidget(header)

        # === КОНТЕНТ (Скролл + Стек) ===
        content_container = QWidget()
        content_container.setStyleSheet("background: transparent;")  # Прозрачный, чтобы видеть фон панели

        # Наш старый StackedWidget теперь живет тут
        self.net_stack = QStackedWidget(content_container)

        # Оборачиваем в Layout с отступами (p-6)
        c_layout = QVBoxLayout(content_container)
        c_layout.setContentsMargins(24, 24, 24, 24)  # p-6
        c_layout.addWidget(self.net_stack)

        main_layout.addWidget(content_container)

        # Инициализируем страницы стека (Login, List, Lobby)
        self.init_network_pages()

    def init_network_pages(self):
        # --- PAGE 0: LOGIN ---
        self.page_login = QWidget()
        l_layout = QVBoxLayout(self.page_login)
        l_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # justify-center
        l_layout.setSpacing(15)

        # Текст "Представьтесь"
        lbl_hint = QLabel("Представьтесь:")
        lbl_hint.setStyleSheet("color: #9ca3af; font-size: 13px;")  # text-gray-400 text-sm
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l_layout.addWidget(lbl_hint)

        # Поле ввода
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Никнейм...")
        self.inp_name.setText(self.user_name)
        # Стили (bg-[#1a1a3a], rounded-xl)
        self.inp_name.setStyleSheet("""
            QLineEdit {
                background-color: #1a1a3a;
                border: 1px solid #2a2a4a;
                border-radius: 12px;
                padding: 12px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #6366f1; } /* focus:border-indigo-500 */
        """)
        l_layout.addWidget(self.inp_name)

        # Кнопка "Войти в сеть"
        btn_login = QPushButton("Войти в сеть")
        btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        # Стили (gradient, rounded-xl, glow)
        btn_login.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #9333ea);
                color: white;
                font-weight: bold;
                border-radius: 12px;
                padding: 12px;
                border: none;
            }
            QPushButton:hover { background-color: #4f46e5; } /* упрощенный ховер */
        """)
        btn_login.clicked.connect(self.do_login_step)
        l_layout.addWidget(btn_login)

        self.net_stack.addWidget(self.page_login)

        # --- PAGE 1: SERVER LIST (LOBBY LIST) ---
        self.page_list = QWidget()
        pl_layout = QVBoxLayout(self.page_list)
        pl_layout.setContentsMargins(0, 0, 0, 0)
        pl_layout.setSpacing(10)

        # Верхняя панель (Заголовок + Обновить)
        top_bar = QHBoxLayout()
        lbl_srv = QLabel("СЕРВЕРЫ")
        lbl_srv.setStyleSheet(
            "color: #6b7280; font-size: 10px; font-weight: bold; letter-spacing: 1px;")  # tracking-widest

        btn_refresh = QPushButton("Обновить")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet("color: #818cf8; border: none; font-size: 11px;")
        btn_refresh.clicked.connect(lambda: self.network.send_json(
            {"type": "login", "name": self.user_name}))  # Повторный логин обновляет список

        top_bar.addWidget(lbl_srv)
        top_bar.addStretch()
        top_bar.addWidget(btn_refresh)
        pl_layout.addLayout(top_bar)

        # Список (QListWidget с кастомными виджетами)
        self.lobby_list_widget = QListWidget()
        self.lobby_list_widget.setStyleSheet("""
                    QListWidget { background: transparent; border: none; outline: none; }
                    QListWidget::item { background: transparent; padding: 0px; margin-bottom: 8px; }
                """)
        pl_layout.addWidget(self.lobby_list_widget)

        # Нижние кнопки
        bottom_box = QFrame()
        bottom_box.setStyleSheet("border-top: 1px solid #2a2a4a; padding-top: 16px;")
        bb_layout = QVBoxLayout(bottom_box)
        bb_layout.setContentsMargins(0, 16, 0, 0)

        btn_create = QPushButton("+ Создать комнату")
        btn_create.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_create.clicked.connect(self.open_create_dialog)
        btn_create.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: 1px solid rgba(99, 102, 241, 0.3); /* indigo-500/30 */
                        color: #a5b4fc; /* indigo-300 */
                        border-radius: 12px;
                        padding: 10px;
                        font-weight: bold;
                        font-size: 13px;
                    }
                    QPushButton:hover { background-color: rgba(99, 102, 241, 0.1); }
                """)

        btn_logout = QPushButton("Выйти")
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logout.clicked.connect(self.do_logout)
        btn_logout.setStyleSheet("color: #6b7280; border: none; font-size: 11px; margin-top: 5px;")

        bb_layout.addWidget(btn_create)
        bb_layout.addWidget(btn_logout, alignment=Qt.AlignmentFlag.AlignHCenter)
        pl_layout.addWidget(bottom_box)

        self.net_stack.addWidget(self.page_list)

        # --- PAGE 2: INSIDE LOBBY ---
        self.page_lobby = QWidget()
        pr_layout = QVBoxLayout(self.page_lobby)
        pr_layout.setContentsMargins(0, 0, 0, 0)
        pr_layout.setSpacing(15)

        # 1. Заголовок комнаты
        room_header = QFrame()
        room_header.setStyleSheet("border-bottom: 1px solid #2a2a4a; padding-bottom: 10px;")
        rh_layout = QHBoxLayout(room_header)
        rh_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_room_name = QLabel("Room Name")
        self.lbl_room_name.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.lbl_room_name.setStyleSheet("color: white; border: none;")

        btn_leave_icon = QPushButton("✕")
        btn_leave_icon.setFixedSize(24, 24)
        btn_leave_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_leave_icon.clicked.connect(self.leave_lobby)
        btn_leave_icon.setStyleSheet("color: #6b7280; border: none; font-weight: bold;")

        rh_layout.addWidget(self.lbl_room_name)
        rh_layout.addStretch()
        rh_layout.addWidget(btn_leave_icon)
        pr_layout.addWidget(room_header)

        # 2. Список игроков
        lbl_players = QLabel("ИГРОКИ")
        lbl_players.setStyleSheet("color: #6b7280; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        pr_layout.addWidget(lbl_players)

        self.room_players_list = QListWidget()
        self.room_players_list.setStyleSheet("""
                    QListWidget { background: transparent; border: none; }
                    QListWidget::item { border-bottom: 1px solid #2a2a4a; padding: 8px 0; }
                """)
        self.room_players_list.setFixedHeight(100)  # Ограничим высоту
        pr_layout.addWidget(self.room_players_list)

        # 3. Выбранная игра
        self.game_info_box = QFrame()
        self.game_info_box.setStyleSheet("""
                    background-color: #1a1a3a; border: 1px solid #2a2a4a; border-radius: 12px;
                """)
        gi_layout = QHBoxLayout(self.game_info_box)

        self.lbl_selected_game_icon = QLabel("🎮")  # Заглушка
        self.lbl_selected_game_name = QLabel("Выберите игру")
        self.lbl_selected_game_name.setStyleSheet("color: #9ca3af; font-weight: 500; border: none;")

        gi_layout.addWidget(self.lbl_selected_game_icon)
        gi_layout.addWidget(self.lbl_selected_game_name)
        gi_layout.addStretch()
        pr_layout.addWidget(self.game_info_box)

        # 4. Чат (Лог + Ввод)
        self.room_log = QListWidget()
        self.room_log.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 8px; color: #9ca3af; font-size: 11px;")
        pr_layout.addWidget(self.room_log)

        chat_inp_box = QHBoxLayout()
        self.chat_inp = QLineEdit()
        self.chat_inp.setPlaceholderText("Сообщение...")
        self.chat_inp.setStyleSheet(
            "background: #1a1a3a; border: 1px solid #2a2a4a; border-radius: 8px; color: white; padding: 6px;")
        self.chat_inp.returnPressed.connect(self.send_chat_msg)  # Отправка по Enter

        btn_send = QPushButton("➤")
        btn_send.setFixedSize(30, 30)
        btn_send.clicked.connect(self.send_chat_msg)
        btn_send.setStyleSheet("color: #818cf8; border: none; font-size: 16px;")

        chat_inp_box.addWidget(self.chat_inp)
        chat_inp_box.addWidget(btn_send)
        pr_layout.addLayout(chat_inp_box)

        # 5. Кнопка Готов
        self.btn_ready = QPushButton("Готов")
        self.btn_ready.setCheckable(True)
        self.btn_ready.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ready.clicked.connect(self.toggle_ready)
        self.btn_ready.setFixedHeight(45)
        # Стили для состояний (Normal / Checked)
        self.btn_ready.setStyleSheet("""
                    QPushButton {
                        background-color: #1a1a3a;
                        color: #9ca3af;
                        border: 1px solid #2a2a4a;
                        border-radius: 12px;
                        font-weight: bold;
                    }
                    QPushButton:checked {
                        background-color: #22c55e; /* green-500 */
                        color: white;
                        border: 1px solid #16a34a;
                    }
                    QPushButton:hover:!checked { border-color: #6b7280; }
                """)
        pr_layout.addWidget(self.btn_ready)

        self.net_stack.addWidget(self.page_lobby)

    def do_login_step(self):
        name = self.inp_name.text().strip()
        if name:
            self.user_name = name

            # Если сокет уже подключен (авто-коннект), шлем логин
            if self.network.isRunning():
                self.network.send_json({"type": "login", "name": name})
                self.net_stack.setCurrentIndex(1)  # Переходим к списку (позже создадим)

                # Меняем индикатор на Зеленый (теперь мы точно в сети как игрок)
                self.conn_indicator.setStyleSheet(self.style_connected)
            else:
                # Если сокета нет - пробуем подключиться (и залогинимся в on_connected)
                self.notifications.show("Ошибка", "Нет соединения с сервером", "error")
        else:
            # Красная рамка (как в JS)
            self.inp_name.setStyleSheet(
                self.inp_name.styleSheet().replace("border: 1px solid #2a2a4a;", "border: 1px solid #ef4444;"))

    def update_lobby_list(self, lobbies):
        self.lobby_list_widget.clear()

        for l in lobbies:
            # Создаем кастомный виджет для элемента
            item_widget = QFrame()
            item_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            item_widget.setFixedHeight(60)
            item_widget.setStyleSheet("""
                QFrame {
                    background-color: #1a1a3a;
                    border: 1px solid #2a2a4a;
                    border-radius: 12px;
                }
                QFrame:hover { background-color: #252540; }
            """)

            # Layout внутри плашки
            h_layout = QHBoxLayout(item_widget)
            h_layout.setContentsMargins(12, 0, 12, 0)

            # Левая часть (Имя + Ping)
            v_layout = QVBoxLayout()
            v_layout.setSpacing(2)

            name_lbl = QLabel(l["name"])
            name_lbl.setStyleSheet(
                "color: #e5e7eb; font-weight: bold; font-size: 13px; border: none; background: transparent;")

            # Ping (заглушка)
            ping_lbl = QLabel("Ping: 5 ms")
            ping_lbl.setStyleSheet("color: #6b7280; font-size: 10px; border: none; background: transparent;")

            v_layout.addWidget(name_lbl)
            v_layout.addWidget(ping_lbl)
            h_layout.addLayout(v_layout)

            h_layout.addStretch()

            # Правая часть (Игроки)
            count_lbl = QLabel(f"{l['players']}/{l['max']}")
            count_lbl.setStyleSheet("""
                background-color: #12122a;
                color: #a5b4fc;
                border: 1px solid rgba(99, 102, 241, 0.2);
                border-radius: 6px;
                padding: 4px 8px;
                font-family: monospace;
                font-size: 11px;
            """)
            h_layout.addWidget(count_lbl)

            # Добавляем в список
            list_item = QListWidgetItem(self.lobby_list_widget)
            list_item.setSizeHint(item_widget.sizeHint())

            # Чтобы клик по виджету обрабатывался, нужно перехватить событие
            # Или использовать QListWidget.itemClicked, но виджет перекроет клик.
            # Сделаем "прозрачную кнопку" поверх или просто используем mousePressEvent в QFrame?
            # Проще: item_widget не перехватывает клики QListWidget, если у него нет кнопок.
            # Но у нас сложный виджет. Сделаем так:

            # Добавляем данные
            list_item.setData(Qt.ItemDataRole.UserRole, l["id"])
            list_item.setData(Qt.ItemDataRole.UserRole + 1, l["private"])

            self.lobby_list_widget.setItemWidget(list_item, item_widget)

    # Метод выхода (Disconnect)
    def do_logout(self):
        self.net_stack.setCurrentIndex(0)  # На страницу логина
        self.conn_indicator.setStyleSheet(self.style_disconnected)  # Красный

    def update_room_ui(self, data):
        self.net_stack.setCurrentIndex(2)  # Переход на страницу лобби

        self.lbl_room_name.setText(data['name'])

        # Обновляем список игроков
        self.room_players_list.clear()
        for p in data["players"]:
            status_color = "#22c55e" if p["ready"] else "#ef4444"  # Зеленый/Красный
            host_icon = "👑 " if p["is_host"] else ""

            # Верстка элемента списка
            item_widget = QWidget()
            il = QHBoxLayout(item_widget)
            il.setContentsMargins(5, 0, 5, 0)

            name = QLabel(f"{host_icon}{p['name']}")
            name.setStyleSheet("color: #e5e7eb; font-weight: 500; border: none;")

            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(f"background-color: {status_color}; border-radius: 4px;")

            il.addWidget(name)
            il.addStretch()
            il.addWidget(dot)

            item = QListWidgetItem(self.room_players_list)
            item.setSizeHint(item_widget.sizeHint())
            self.room_players_list.setItemWidget(item, item_widget)

        # Игра
        sel_game = data["selected_game"]
        if sel_game:
            # Находим название
            title = next((g["title"] for g in GAMES_CONFIG if g["id"] == sel_game), "Неизвестно")
            self.lbl_selected_game_name.setText(title)
            self.lbl_selected_game_name.setStyleSheet("color: #e5e7eb; font-weight: bold; border: none;")
            self.game_info_box.setStyleSheet(
                "background-color: #312e81; border: 1px solid #4f46e5; border-radius: 12px;")  # Подсветка индиго
        else:
            self.lbl_selected_game_name.setText("Выберите игру слева")
            self.lbl_selected_game_name.setStyleSheet("color: #9ca3af; font-weight: 500; border: none;")
            self.game_info_box.setStyleSheet(
                "background-color: #1a1a3a; border: 1px solid #2a2a4a; border-radius: 12px;")

    def toggle_ready(self):
        status = self.btn_ready.isChecked()
        self.btn_ready.setText("Я Готов!" if status else "Не готов")
        self.network.send_json({"type": "toggle_ready", "status": status})

    def send_chat_msg(self):
        msg = self.chat_inp.text().strip()
        if msg:
            self.network.send_json({"type": "chat_msg", "text": msg})
            self.chat_inp.clear()
            # Добавляем в лог сразу (опционально, или ждать от сервера)
            self.add_to_log(f"Вы: {msg}")

    def set_game_status(self, is_running, game_title=""):
        if is_running:
            self.status_stack.setCurrentIndex(1)  # Показываем Running
            self.lbl_running_name.setText(game_title)
            self.btn_stop_game.show()
        else:
            self.status_stack.setCurrentIndex(0)  # Показываем Idle
            self.btn_stop_game.hide()

    def load_games(self):
        for game in GAMES_CONFIG:
            card = GameCard(game, self.on_game_click)
            self.grid_layout.addWidget(card)

    # --- СЕТЕВЫЕ СОБЫТИЯ ---
    def fetch_server_list_and_connect(self):
        def worker():
            try:
                import time
                base_url = "https://gist.githubusercontent.com/ruPaTRiK/fba2f42d20c7bb8893793928c3257880/raw/servers.json"

                url = f"{base_url}?t={int(time.time())}"

                req = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                )

                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE


                with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
                    text_data = response.read().decode('utf-8')
                    print(f"DEBUG: Пришло: {text_data}")
                    data = json.loads(text_data)

                    self.servers_loaded.emit(data)

            except Exception as e:
                self.servers_loaded.emit([])

        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()

    def run_update_thread(self, updater, url):
        def progress_callback(percent):
            self.update_progress_signal.emit(percent)

        success = updater.download_update(url, progress_callback)

        # Завершение
        self.update_finished_signal.emit(success)

    def finish_update(self, success):
        if hasattr(self, 'update_dlg'):
            self.update_dlg.close()

        if success:
            self.notifications.show("Обновление", "Установка...", "success")
            # Даем секунду на отрисовку уведомления
            QTimer.singleShot(1000, self.updater_instance.restart_and_replace)
        else:
            self.notifications.show("Ошибка", "Не удалось скачать обновление", "error")

    def on_update_progress(self, percent):
        if hasattr(self, 'update_dlg'):
            self.update_dlg.set_progress(percent)

    def finish_loading_servers(self, raw_data):
        servers = []
        print(raw_data)
        try:
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

                        self.updater_instance = updater

                        t = threading.Thread(target=self.run_update_thread, args=(updater, download_url))
                        t.daemon = True
                        t.start()
                        return

            elif isinstance(raw_data, list):
                servers = raw_data
        except Exception as e:
            print(f"Ошибка в блоке обновления: {e}")

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
        self.conn_indicator.setStyleSheet(self.style_connected)
        self.conn_indicator.setToolTip("Подключено")

    def on_disconnected(self):
        self.notifications.show("Сервер", "Соединение разорвано", "error")
        self.stack.setCurrentIndex(0)
        self.lobby_list_widget.clear()
        self.conn_indicator.setStyleSheet(self.style_disconnected)
        self.conn_indicator.setToolTip("Не подключено")

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
        if self.active_game:
            self.active_game.close()

        self.active_game = game_window
        self.set_game_status(True, title)

        game_window.destroyed.connect(lambda: self.set_game_status(False))

    def close_active_game(self):
        if self.active_game:
            self.active_game.close()

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
        if not hasattr(self, 'resize_timer'):
            self.resize_timer = QTimer()
            self.resize_timer.setSingleShot(True)
            self.resize_timer.timeout.connect(self.reflow_games_grid)

        self.resize_timer.start(35)
        super().resizeEvent(event)

    def reflow_games_grid(self):
        available_width = self.width() - 70 - 320 - 60
        if available_width < 250: available_width = 250

        card_width = 220
        spacing = 25

        cols = available_width // (card_width + spacing)
        if cols < 1: cols = 1

        widgets = []
        for i in range(self.grid_layout.count()):
            widgets.append(self.grid_layout.itemAt(i).widget())

        for w in widgets:
            if w: w.setParent(None)

        row, col = 0, 0
        for w in widgets:
            if w:
                self.grid_layout.addWidget(w, row, col)
                col += 1
                if col >= cols:
                    col = 0
                    row += 1

    def update_game_opacity(self, opacity):
        if self.active_game:
            self.active_game.setWindowOpacity(opacity)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    l = Launcher()
    l.show()
    sys.exit(app.exec())