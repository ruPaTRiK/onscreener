import sys
import os
import json
import urllib.request
import threading
import ssl

from core.updater import AutoUpdater
from core.update_dialog import UpdateProgressDialog

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QGridLayout, QScrollArea, QFrame,
                             QLineEdit, QStackedWidget, QListWidget, QListWidgetItem,
                             QMessageBox, QButtonGroup, QGraphicsDropShadowEffect, QSlider,
                             QCheckBox, QComboBox)
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtCore import Qt, QTimer, QDateTime, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint

from core.base_window import OverlayWindow
from core.network import NetworkClient
from core.coin_dialog import CoinFlipDialog
from core.lobby_dialogs import CreateLobbyDialog, PasswordDialog
from core.notifications import NotificationManager
from games_config import GAMES_CONFIG

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
        self.is_connecting = False

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
        self.setup_settings_page()

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
                        border: 1px solid #2a2a4a;
                        border-right: none;
                    }
                """)
        header.setFixedHeight(70)  # p-6 (24px) ~ 70-80px
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)

        # Иконка (текстом 🌍) и Заголовок
        title_box = QHBoxLayout()
        title_box.setSpacing(10)

        icon_lbl = QLabel("🌍")  # Заглушка SVG
        icon_lbl.setStyleSheet("font-size: 18px; color: #818cf8; border: none")  # indigo-400

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
        pr_layout.setSpacing(0)  # Отступы контролируем внутри элементов

        # 1. HEADER (Комната и Игра)
        header_container = QFrame()
        header_container.setStyleSheet("QFrame {padding-bottom: 10px; margin-bottom: 10px; border-bottom: 1px solid #2a2a4a;}"
                                       "QFrame > * {padding-bottom: 2px; margin-bottom: 2px; border: none;}")
        hc_layout = QVBoxLayout(header_container)
        hc_layout.setContentsMargins(0, 0, 0, 0)
        hc_layout.setSpacing(4)

        lbl_subtitle = QLabel("КОМНАТА")
        lbl_subtitle.setStyleSheet(
            "color: #6b7280; font-size: 10px; font-weight: bold; letter-spacing: 1px;")  # tracking-widest
        hc_layout.addWidget(lbl_subtitle)

        self.lbl_room_name = QLabel("Room Name")
        self.lbl_room_name.setFont(QFont("Arial", 14, QFont.Weight.Bold))  # text-lg
        self.lbl_room_name.setStyleSheet("color: white; border: none; padding-left: 0px;")
        hc_layout.addWidget(self.lbl_room_name)

        # Строка с игрой
        game_row = QHBoxLayout()
        lbl_game_title = QLabel("Игра:")
        lbl_game_title.setStyleSheet("color: #9ca3af; font-size: 12px;")
        self.lbl_selected_game_name = QLabel("Не выбрана")
        self.lbl_selected_game_name.setStyleSheet(
            "color: #818cf8; font-size: 12px; font-weight: bold;")  # text-indigo-400
        game_row.addWidget(lbl_game_title)
        game_row.addWidget(self.lbl_selected_game_name)
        game_row.addStretch()
        hc_layout.addLayout(game_row)

        pr_layout.addWidget(header_container)

        # 2. СПИСОК ИГРОКОВ
        # Заголовок списка
        player_header = QHBoxLayout()
        lbl_p_title = QLabel("ИГРОКИ")
        lbl_p_title.setStyleSheet("color: #6b7280; font-size: 10px; font-weight: bold; letter-spacing: 1px; margin-bottom: 6px;")
        self.lbl_player_count = QLabel("0/8")
        self.lbl_player_count.setStyleSheet("color: #6b7280; font-size: 10px; font-weight: bold;")
        player_header.addWidget(lbl_p_title)
        player_header.addStretch()
        player_header.addWidget(self.lbl_player_count)
        pr_layout.addLayout(player_header)

        # Сам список
        self.room_players_list = QListWidget()
        self.room_players_list.setStyleSheet("background: transparent; border: none; outline: none;")
        self.room_players_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.room_players_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.room_players_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        pr_layout.addWidget(self.room_players_list)

        # 3. Чат и лог
        lbl_chat = QLabel("ЧАТ")
        lbl_chat.setStyleSheet(
            "color: #6b7280; font-size: 10px; font-weight: bold; letter-spacing: 1px; margin-top: 5px; margin-bottom: 6px;")
        pr_layout.addWidget(lbl_chat)

        self.room_log = QListWidget()
        self.room_log.setStyleSheet(
            "background: rgba(0, 0, 0, 0.2); border: 1px solid #2a2a4a; border-bottom: none;"
            "border-top-left-radius: 10px; border-top-right-radius: 10px; color: #9ca3af; font-size: 11px;")
        self.room_log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.room_log.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.room_log.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Автоскролл
        self.room_log.model().rowsInserted.connect(self.room_log.scrollToBottom)
        pr_layout.addWidget(self.room_log)

        chat_box = QHBoxLayout()
        self.chat_inp = QLineEdit()
        self.chat_inp.setPlaceholderText("Сообщение...")
        self.chat_inp.setStyleSheet(
            "background: #1a1a3a; border: 1px solid #2a2a4a; border-top: none; border-right: none;"
            "border-bottom-left-radius: 10px; color: white; padding: 6px;")
        self.chat_inp.returnPressed.connect(self.send_chat_msg)

        btn_send = QPushButton("➤")
        btn_send.setFixedSize(31, 31)
        btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_send.clicked.connect(self.send_chat_msg)
        btn_send.setStyleSheet("color: #818cf8; border: 1px solid #2a2a4a; border-top: none; border-left: none;"
                               "border-bottom-right-radius: 10px; font-size: 24px;")

        chat_box.addWidget(self.chat_inp)
        chat_box.addWidget(btn_send)
        pr_layout.addLayout(chat_box)

        # 4. FOOTER (Кнопки)
        footer_container = QWidget()
        f_layout = QVBoxLayout(footer_container)
        f_layout.setContentsMargins(0, 16, 0, 0)  # mt-auto pt-4
        f_layout.setSpacing(10)

        # Кнопка ГОТОВ
        self.btn_ready = QPushButton("ГОТОВ")
        self.btn_ready.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ready.setFixedHeight(45)  # py-3
        self.btn_ready.clicked.connect(self.toggle_ready)
        # Стиль по умолчанию (Не готов)
        self.btn_ready.setStyleSheet("""
                    QPushButton {
                        background-color: #2a2a4a;
                        color: #d1d5db; /* gray-300 */
                        border-radius: 12px;
                        font-weight: bold;
                        border: none;
                    }
                    QPushButton:hover { background-color: #35355a; }
                """)
        f_layout.addWidget(self.btn_ready)

        # Кнопка ПОКИНУТЬ
        btn_leave = QPushButton("Покинуть")
        btn_leave.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_leave.setFixedHeight(35)  # py-2
        btn_leave.clicked.connect(self.leave_lobby)
        btn_leave.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: 1px solid rgba(239, 68, 68, 0.3); /* red-500/30 */
                        color: #f87171; /* red-400 */
                        border-radius: 12px;
                        font-weight: 600; /* font-semibold */
                        font-size: 13px; /* text-sm */
                    }
                    QPushButton:hover { background-color: rgba(239, 68, 68, 0.1); }
                """)
        f_layout.addWidget(btn_leave)

        pr_layout.addWidget(footer_container)

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
            # Создаем элемент списка
            list_item = QListWidgetItem(self.lobby_list_widget)

            # --- ВИДЖЕТ ЭЛЕМЕНТА ---
            # Мы наследуемся от QFrame, чтобы переопределить клик
            class LobbyWidget(QFrame):
                def __init__(self, parent_launcher, lobby_data):
                    super().__init__()
                    self.launcher = parent_launcher
                    self.lobby_data = lobby_data
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                    self.setFixedHeight(60)
                    self.setStyleSheet("""
                                QFrame {
                                    background-color: #1a1a3a;
                                    border: 1px solid #2a2a4a;
                                    border-radius: 12px;
                                }
                                QFrame:hover { background-color: #252540; border-color: #6366f1; }
                            """)

                    # Лейаут (тот же, что был)
                    h_layout = QHBoxLayout(self)
                    h_layout.setContentsMargins(12, 0, 12, 0)

                    v_layout = QVBoxLayout()
                    v_layout.setSpacing(2)
                    name_lbl = QLabel(l["name"])
                    name_lbl.setStyleSheet("color: #e5e7eb; font-weight: bold; border: none; background: transparent;")
                    v_layout.addWidget(name_lbl)
                    h_layout.addLayout(v_layout)

                    h_layout.addStretch()

                    # Замок, если есть
                    if l["private"]:
                        lock = QLabel("🔒")
                        lock.setStyleSheet("border: none; background: transparent; color: #fbbf24;")
                        h_layout.addWidget(lock)

                    count_lbl = QLabel(f"{l['players']}/{l['max']}")
                    count_lbl.setStyleSheet("""
                                background-color: #12122a; color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.2);
                                border-radius: 6px; padding: 2px 8px; margin: 14px 0px; font-size: 11px;
                            """)
                    h_layout.addWidget(count_lbl)

                # ПЕРЕХВАТ ДВОЙНОГО КЛИКА
                def mouseDoubleClickEvent(self, event):
                    if event.button() == Qt.MouseButton.LeftButton:
                        # Вызываем метод Лаунчера напрямую
                        self.launcher.join_lobby_by_data(self.lobby_data)

            # Создаем и добавляем
            item_widget = LobbyWidget(self, l)
            list_item.setSizeHint(item_widget.sizeHint())
            self.lobby_list_widget.setItemWidget(list_item, item_widget)

    def join_lobby_by_data(self, l_data):
        lid = l_data["id"]
        is_private = l_data["private"]
        pwd = ""

        if is_private:
            dlg = PasswordDialog(self)
            if dlg.exec():
                pwd = dlg.get_password()
            else:
                return  # Отмена

        self.network.send_json({"type": "join_lobby", "lobby_id": lid, "password": pwd})

    # Метод выхода (Disconnect)
    def do_logout(self):
        self.net_stack.setCurrentIndex(0)  # На страницу логина
        self.conn_indicator.setStyleSheet(self.style_disconnected)  # Красный

    def update_room_ui(self, data):
        self.net_stack.setCurrentIndex(2)

        self.current_lobby_id = data["lobby_id"]
        self.is_host = data["am_i_host"]

        self.lbl_room_name.setText(data['name'])

        # Обновляем игру
        sel_game = data["selected_game"]
        if sel_game:
            title = next((g["title"] for g in GAMES_CONFIG if g["id"] == sel_game), "Неизвестно")
            self.lbl_selected_game_name.setText(title)
            # Подсвечиваем в списке слева
            self.deselect_all_games()
            if sel_game in self.game_cards:
                self.game_cards[sel_game].set_selected(True)
        else:
            self.lbl_selected_game_name.setText("Не выбрана")
            self.deselect_all_games()

        # Обновляем список игроков
        self.room_players_list.clear()

        # Ищем себя в списке для обновления кнопки
        my_ready_status = False

        current_name = self.user_name

        self.room_players_list.setSpacing(5)

        for p in data["players"]:
            is_me = (p["name"] == current_name)

            # Обновляем свою кнопку готовности, если данные пришли с сервера
            if is_me:
                my_ready_status = p["ready"]
                self.btn_ready.blockSignals(True)
                self.btn_ready.setChecked(p["ready"])
                self.btn_ready.setText("ВЫ ГОТОВЫ" if p["ready"] else "ГОТОВ")
                self.btn_ready.blockSignals(False)

            # Виджет игрока
            item_widget = QFrame()
            item_widget.setFixedHeight(50)
            item_widget.setStyleSheet("""
                        QFrame {
                            background-color: #1a1a3a;
                            border: 1px solid #2a2a4a;
                            border-radius: 8px;
                        }
                    """)

            h_layout = QHBoxLayout(item_widget)
            h_layout.setContentsMargins(10, 0, 10, 0)

            # Левая часть
            left_box = QHBoxLayout()
            left_box.setSpacing(10)

            # Аватар
            avatar = QLabel(p["name"][0].upper())
            avatar.setFixedSize(28, 28)
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar.setStyleSheet("""
                        background-color: #374151; color: white; font-weight: bold; border-radius: 6px; border: none;
                    """)
            left_box.addWidget(avatar)

            # Имя + Корона
            name_text = p["name"]
            # Определяем цвет имени
            text_color = "#818cf8" if is_me else "#e5e7eb"  # Indigo / White

            name_lbl = QLabel(name_text)
            name_lbl.setStyleSheet(f"color: {text_color}; font-weight: 600; border: none; background: transparent;")
            left_box.addWidget(name_lbl)

            # --- ДОБАВЛЯЕМ КОРОНУ ---
            if p["is_host"]:
                crown = QLabel("👑")
                crown.setStyleSheet("font-size: 14px; border: none; background: transparent;")
                crown.setToolTip("Создатель комнаты")
                left_box.addWidget(crown)
            # ------------------------

            h_layout.addLayout(left_box)
            h_layout.addStretch()

            # Правая часть: Статус
            status_lbl = QLabel()
            if p["ready"]:
                status_lbl.setText("ГОТОВ")
                status_lbl.setStyleSheet("""
                            color: #4ade80; background-color: rgba(74, 222, 128, 0.1); 
                            border: 1px solid rgba(74, 222, 128, 0.2); border-radius: 4px; padding: 2px 8px; margin: 14px 0px;
                            font-weight: bold; font-size: 10px;
                        """)
            else:
                status_lbl.setText("ЖДЕТ")
                status_lbl.setStyleSheet("""
                            color: #9ca3af; background-color: #1f2937;
                            border: 1px solid #374151; border-radius: 4px; padding: 2px 8px; margin: 14px 0px;
                            font-weight: bold; font-size: 10px;
                        """)

            h_layout.addWidget(status_lbl)

            item = QListWidgetItem(self.room_players_list)
            item.setSizeHint(item_widget.sizeHint())
            self.room_players_list.setItemWidget(item, item_widget)

        self.lbl_player_count.setText(f"{len(data['players'])}/8")

        # Обновляем стиль кнопки "Готов"
        self.update_ready_button_style(my_ready_status)

    def update_ready_button_style(self, is_ready):
        # Чтобы не вызывать бесконечный цикл сигналов
        self.btn_ready.blockSignals(True)
        # Мы используем это как флаг состояния, хоть кнопка и не checkable
        # Но для стиля проще перезаписывать stylesheet

        if is_ready:
            self.btn_ready.setText("ВЫ ГОТОВЫ")
            self.btn_ready.setStyleSheet("""
                QPushButton {
                    background-color: #16a34a; /* green-600 */
                    color: white;
                    border-radius: 12px;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover { background-color: #22c55e; }
            """)
        else:
            self.btn_ready.setText("ГОТОВ")
            self.btn_ready.setStyleSheet("""
                QPushButton {
                    background-color: #2a2a4a;
                    color: #d1d5db;
                    border-radius: 12px;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover { background-color: #35355a; }
            """)
        self.btn_ready.blockSignals(False)

    def toggle_ready(self):
        current_text = self.btn_ready.text()
        new_status = (current_text == "ГОТОВ")

        self.network.send_json({"type": "toggle_ready", "status": new_status})

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


    # --- НАСТРОЙКИ ---
    def setup_settings_page(self):
        self.page_settings = QWidget()
        # Основной Layout страницы
        main_layout = QVBoxLayout(self.page_settings)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(30)

        # Заголовок
        lbl_title = QLabel("Настройки")
        lbl_title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: white;")
        main_layout.addWidget(lbl_title)

        # Скролл (на случай если настроек будет много)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setSpacing(40)

        # === СЕКЦИЯ 1: ПРИЛОЖЕНИЕ ===
        sec_app = self.create_settings_section("ПРИЛОЖЕНИЕ")
        sec_app_layout = sec_app.layout()

        # Громкость
        sec_app_layout.addWidget(QLabel("Громкость звука", styleSheet="color: #ccc; font-size: 14px;"))
        self.slider_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(int(SettingsManager().get("volume") * 100))
        self.slider_vol.valueChanged.connect(self.update_volume)
        # Стиль слайдера
        self.slider_vol.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #333; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #6366f1; border-radius: 2px; }
            QSlider::handle:horizontal { background: white; width: 16px; margin: -6px 0; border-radius: 8px; }
        """)
        sec_app_layout.addWidget(self.slider_vol)

        # Mute
        self.check_mute = QCheckBox("Выключить звук")
        self.check_mute.setChecked(SettingsManager().get("mute"))
        self.check_mute.toggled.connect(self.update_mute)
        self.check_mute.setStyleSheet("""
            QCheckBox { color: white; font-size: 14px; spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #555; background: #1a1a3a; }
            QCheckBox::indicator:checked { background: #6366f1; border-color: #6366f1; }
        """)
        sec_app_layout.addWidget(self.check_mute)

        # Прозрачность
        sec_app_layout.addWidget(
            QLabel("Прозрачность окон игр", styleSheet="color: #ccc; font-size: 14px; margin-top: 10px;"))
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(20, 100)
        self.slider_opacity.setValue(int(SettingsManager().get("window_opacity") * 100))
        self.slider_opacity.valueChanged.connect(self.update_opacity)
        self.slider_opacity.setStyleSheet(self.slider_vol.styleSheet())
        sec_app_layout.addWidget(self.slider_opacity)

        content_layout.addWidget(sec_app)

        # === СЕКЦИЯ 2: СЕТЬ ===
        sec_net = self.create_settings_section("СЕТЬ И СЕРВЕРЫ")
        net_layout = sec_net.layout()

        # Выпадающий список серверов
        net_layout.addWidget(QLabel("Сервер подключения", styleSheet="color: #ccc; font-size: 14px;"))
        self.combo_servers = QComboBox()
        self.combo_servers.setStyleSheet("""
            QComboBox { padding: 10px; background: #1a1a3a; color: white; border: 1px solid #2a2a4a; border-radius: 8px; font-size: 14px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #1a1a3a; color: white; selection-background-color: #6366f1; padding: 5px; }
        """)
        self.combo_servers.currentIndexChanged.connect(self.on_server_combo_changed)
        net_layout.addWidget(self.combo_servers)

        # Поле ручного ввода (скрыто по умолчанию)
        self.inp_custom_ip = QLineEdit()
        self.inp_custom_ip.setPlaceholderText("IP:PORT (например 127.0.0.1:5555)")
        self.inp_custom_ip.setStyleSheet("""
            QLineEdit { background: #1a1a3a; color: white; border: 1px solid #2a2a4a; border-radius: 8px; padding: 10px; }
            QLineEdit:focus { border-color: #6366f1; }
        """)
        self.inp_custom_ip.hide()
        net_layout.addWidget(self.inp_custom_ip)

        # Кнопки управления сервером
        btn_box = QHBoxLayout()
        btn_refresh = QPushButton("🔄 Обновить список")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self.fetch_server_list_and_connect)  # Переиспользуем логику
        btn_refresh.setStyleSheet(
            "color: #818cf8; background: transparent; border: none; text-align: left; font-weight: bold;")

        btn_apply_server = QPushButton("Применить и Подключиться")
        btn_apply_server.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_apply_server.clicked.connect(self.apply_server_change)
        btn_apply_server.setStyleSheet("""
            QPushButton { background-color: #2a2a4a; color: white; border-radius: 8px; padding: 10px 20px; font-weight: bold; border: 1px solid #2a2a4a; }
            QPushButton:hover { background-color: #6366f1; border-color: #6366f1; }
        """)

        btn_box.addWidget(btn_refresh)
        btn_box.addStretch()
        btn_box.addWidget(btn_apply_server)
        net_layout.addLayout(btn_box)

        content_layout.addWidget(sec_net)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Добавляем страницу в стек (индекс 2, так как 0=Games, 1=Friends)
        # Или индекс 3, если настройки были последними.
        # В setup_sidebar у нас было: lambda: self.main_stack.setCurrentIndex(2)
        # Значит добавляем как 3-й виджет.
        self.main_stack.addWidget(self.page_settings)

    def create_settings_section(self, title):
        frame = QFrame()
        frame.setStyleSheet("QFrame {background-color: rgba(255,255,255,0.03); border-radius: 12px;}"
                            "QFrame > * {background-color: none}")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        lbl = QLabel(title)
        lbl.setStyleSheet("color: #6b7280; font-size: 12px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(lbl)

        return frame

    # --- ЛОГИКА НАСТРОЕК ---
    def update_volume(self, val):
        vol = val / 100.0
        SettingsManager().set("volume", vol)
        SoundManager().set_volume(vol)

    def update_mute(self, checked):
        SettingsManager().set("mute", checked)
        SoundManager().muted = checked

    def update_opacity(self, val):
        opacity = val / 100.0
        SettingsManager().set("window_opacity", opacity)
        if self.active_game:
            self.active_game.setWindowOpacity(opacity)

    def on_server_combo_changed(self, index):
        data = self.combo_servers.currentData()
        if data == "custom":
            self.inp_custom_ip.show()
        else:
            self.inp_custom_ip.hide()

    def update_server_combo_ui(self, servers_data):
        # Этот метод вызывается после скачивания списка (из finish_loading_servers)
        self.combo_servers.blockSignals(True)
        self.combo_servers.clear()

        # Добавляем серверы
        for s in servers_data:
            ip_data = f"{s['ip']}:{s.get('port', 5555)}"
            self.combo_servers.addItem(s['name'], ip_data)

        self.combo_servers.addItem("Свой сервер...", "custom")

        # Выбираем текущий активный (если есть в списке)
        # Или первый по умолчанию
        self.combo_servers.setCurrentIndex(0)
        self.combo_servers.blockSignals(False)

    def apply_server_change(self):
        data = self.combo_servers.currentData()
        ip, port = "", 5555

        if data == "custom":
            raw = self.inp_custom_ip.text().strip()
            if ":" in raw:
                ip, port = raw.split(":")
                port = int(port)
            else:
                ip = raw
        elif data:
            ip, port = data.split(":")
            port = int(port)

        if ip:
            self.notifications.show("Сервер", f"Переподключение к {ip}...", "info")
            self.is_connecting = True
            self.network.connect_to(ip, port)

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

        if hasattr(self, 'combo_servers'):
            self.update_server_combo_ui(servers)

        if self.servers_list:
            srv = self.servers_list[0]
            ip = srv['ip']
            port = srv.get('port', 5555)

            self.network.disconnect()

            self.notifications.show("Сервер", f"Подключение к: {srv['name']}...", "info")
            QTimer.singleShot(500, lambda: self.network.connect_to(ip, port))
        else:
            self.network.connect_to("127.0.0.1", 5555)

    #def open_server_dialog(self):
    #    dlg = ServerSelectDialog(self, self.servers_list)
    #    if dlg.exec():
    #        ip = dlg.result_ip
    #        port = dlg.result_port
    #        if ip:
    #            self.network.disconnect()  # Рвем старое
    #
    #            self.notifications.show("Сервер", f"Переподключение к {ip}...", "info")
    #            # Небольшая задержка перед новым коннектом
    #            QTimer.singleShot(500, lambda: self.network.connect_to(ip, port))

    def on_connected(self):
        self.is_connecting = False
        self.network.send_json({"type": "login", "name": self.inp_name.text()})
        self.notifications.show("Сервер", "Подключено успешно!", "success")
        self.conn_indicator.setStyleSheet(self.style_connected)
        self.conn_indicator.setToolTip("Подключено")

    def on_disconnected(self):
        if self.is_connecting:
            return
        self.notifications.show("Сервер", "Соединение разорвано", "error")
        self.net_stack.setCurrentIndex(0)
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
            self.net_stack.setCurrentIndex(0)
            self.current_lobby_id = None
            self.deselect_all_games()

        elif dtype == "error":
            self.notifications.show("Ошибка", data["msg"], "error")

        elif dtype == "left_lobby_success":
            self.notifications.show("Лобби", "Вы покинули комнату", "info")

            self.net_stack.setCurrentIndex(1)

            self.current_lobby_id = None
            self.is_host = False
            self.deselect_all_games()

            self.btn_ready.setChecked(False)
            self.btn_ready.setText("ГОТОВ")

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

        elif dtype == "chat_msg":
            sender = data.get("sender", "Неизвестный")
            text = data.get("text", "")
            self.add_to_log(f"{sender}: {text}")

    def on_client_data(self, data):
        if data.get("type") == "game_move" and self.active_game:
            self.process_log_entry(data, "Вы")
        if data.get("type") == "game_emote":
            emoji = data.get("emoji")
            self.add_to_log(f"Вы: {emoji}")

    def update_name(self):
        if self.network.is_running:
            self.network.send_json({"type": "login", "name": self.inp_name.text()})

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

    def leave_lobby(self):
        self.network.send_json({"type": "leave_lobby"})
        self.btn_ready.setChecked(False)
        self.inp_name.setEnabled(True)

    def send_ready_status(self, checked):
        self.network.send_json({"type": "toggle_ready", "status": checked})

    def send_chat_msg(self):
        text = self.chat_inp.text().strip()
        if text:
            if self.network.is_running:
                self.network.send_json({"type": "chat_msg", "text": text})

            self.add_to_log(f"Вы: {text}")

            self.chat_inp.clear()

    # --- КЛИКИ ПО ИГРАМ ---
    def on_game_click(self, game_data):
        if self.is_game_running:
            self.notifications.show("Внимание", "Игра уже запущена", "warning")
            return

        if self.current_lobby_id:
            # МЫ В ЛОББИ (ОНЛАЙН)
            if self.is_host:
                # Отправляем выбор игры на сервер
                self.network.send_json({"type": "select_game", "game_id": game_data["id"]})
            else:
                self.notifications.show("Внимание", "Только хост выбирает игру", "warning")
        else:
            # МЫ НЕ В ЛОББИ (ОФФЛАЙН/СОЛО)
            game_class = game_data["class"]
            win = game_class()
            win.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

            op = SettingsManager().get("window_opacity")
            if op is None: op = 1.0
            win.setWindowOpacity(float(op))

            win.show()
            self.add_active_game_widget(win, game_data["title"])

    def deselect_all_games(self):
        for card in self.game_cards.values():
            card.set_selected(False)

    def launch_online_game(self, game_id, my_color):

        try:
            game_conf = next((g for g in GAMES_CONFIG if g["id"] == game_id), None)
            if not game_conf:
                print(f"ERROR: Игра {game_id} не найдена в конфиге!")
                return

            self.active_game_id = game_id

            # Лог разделитель
            if hasattr(self, 'room_log') and self.room_log is not None:
                if self.room_log.count() > 0:
                    self.room_log.addItem(QListWidgetItem(""))
                    self.room_log.addItem(QListWidgetItem("--- НОВАЯ ИГРА ---"))
                    self.room_log.addItem(QListWidgetItem(""))

            game_class = game_conf["class"]
            play_as_white = (my_color == 'white')

            self.active_game = game_class(is_online=True, is_host=play_as_white, network_client=self.network)

            # Настройки окна
            self.active_game.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

            # Прозрачность
            try:
                from core.settings import SettingsManager
                op = SettingsManager().get("window_opacity")
                self.active_game.setWindowOpacity(op)
            except:
                pass

            # Показываем
            self.active_game.show()

            # Обновляем статус внизу
            self.add_active_game_widget(self.active_game, f"{game_conf['title']} (Online)")

            self.is_game_running = True
            self.add_to_log(f"Игра {game_conf['title']} началась!")

        except Exception as e:
            print(f"CRITICAL ERROR IN LAUNCH_ONLINE_GAME: {e}")
            import traceback
            traceback.print_exc()
            self.notifications.show("Ошибка запуска", str(e), "error")

    def add_active_game_widget(self, game_window, title):
        if self.active_game and self.active_game != game_window:
            try:
                self.active_game.close()
            except:
                pass

        self.active_game = game_window

        self.set_game_status(True, title)

        try:
            game_window.destroyed.disconnect()
        except:
            pass

        game_window.destroyed.connect(lambda: self.remove_active_game_widget(id(game_window)))

    def close_active_game(self):
        if self.active_game:
            self.active_game.close()

    def remove_active_game_widget(self, window_id):

        if self.active_game and id(self.active_game) == window_id:
            self.active_game = None
            self.active_game_id = None
            self.is_game_running = False

            # Сбрасываем статус внизу (Серая точка)
            self.set_game_status(False)

            # Снимаем готовность в лобби
            if self.current_lobby_id:
                self.btn_ready.setChecked(False)
                self.notifications.show("Лобби", "Игра завершена. Статус: Не готов", "info")
                self.add_to_log("Игра завершена")

    def add_to_log(self, message):
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