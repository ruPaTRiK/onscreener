from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QLabel, QSlider, QCheckBox,
                             QPushButton, QHBoxLayout, QWidget, QGraphicsOpacityEffect)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor

from core.settings import SettingsManager
from core.sound_manager import SoundManager


class SettingsPanel(QFrame):
    # Сигнал, чтобы сообщить лаунчеру об изменении прозрачности (для обновления активной игры)
    opacity_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager()
        self.sound = SoundManager()

        # Настройка внешнего вида панели
        self.setFixedWidth(0)  # Скрыта по умолчанию
        self.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border-left: 1px solid #444;
            }
            QLabel { color: white; font-weight: bold; font-size: 14px; border: none; }
            QCheckBox { color: white; border: none; }
            QSlider::handle:horizontal {
                background: #3498db; width: 16px; margin: -5px 0; border-radius: 8px;
            }
        """)

        # Основной Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)

        # Заголовок и кнопка закрытия
        header_layout = QHBoxLayout()
        lbl_title = QLabel("Настройки")
        lbl_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header_layout.addWidget(lbl_title)

        btn_close = QPushButton("✕")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet("background: transparent; color: #aaa; border: none; font-size: 18px;")
        btn_close.clicked.connect(self.toggle)  # Закрыть при нажатии
        header_layout.addWidget(btn_close)

        self.layout.addLayout(header_layout)

        # --- ГРОМКОСТЬ ---
        self.layout.addWidget(QLabel("Громкость"))
        self.slider_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_vol.setRange(0, 100)
        self.slider_vol.setValue(int(self.settings.get("volume") * 100))
        self.slider_vol.valueChanged.connect(self.update_volume)
        self.layout.addWidget(self.slider_vol)

        self.check_mute = QCheckBox("Выключить звук")
        self.check_mute.setChecked(self.settings.get("mute"))
        self.check_mute.toggled.connect(self.update_mute)
        self.layout.addWidget(self.check_mute)

        # --- ПРОЗРАЧНОСТЬ ИГР ---
        self.layout.addWidget(QLabel("Прозрачность окон игр"))
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(20, 100)
        self.slider_opacity.setValue(int(self.settings.get("window_opacity") * 100))
        self.slider_opacity.valueChanged.connect(self.update_opacity)
        self.layout.addWidget(self.slider_opacity)

        self.layout.addStretch()  # Прижать всё вверх

        # Анимация ширины
        self.anim = QPropertyAnimation(self, b"maximumWidth")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.is_open = False

    def toggle(self):
        if self.is_open:
            # Закрываем
            self.anim.setStartValue(300)
            self.anim.setEndValue(0)
            self.is_open = False
        else:
            # Открываем
            self.anim.setStartValue(0)
            self.anim.setEndValue(300)
            self.is_open = True

        self.anim.start()

    def update_volume(self, val):
        vol = val / 100.0
        self.settings.set("volume", vol)
        self.sound.set_volume(vol)

    def update_mute(self, checked):
        self.settings.set("mute", checked)
        self.sound.muted = checked

    def update_opacity(self, val):
        opacity = val / 100.0
        self.settings.set("window_opacity", opacity)
        self.opacity_changed.emit(opacity)  # Шлем сигнал в лаунчер