from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QPushButton, QGraphicsOpacityEffect, QStyleOption, QStyle
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize
from PyQt6.QtGui import QIcon, QFont, QColor, QPainter


class ToastNotification(QWidget):
    def __init__(self, parent, title, message, type_name="info"):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Настройки цветов и иконок
        colors = {
            "success": "#2ecc71",
            "error": "#e74c3c",
            "warning": "#f39c12",
            "info": "#3498db"
        }
        accent_color = colors.get(type_name, "#3498db")

        # Основной стиль виджета
        self.setObjectName("ToastWidget")
        self.setStyleSheet(f"""
            #ToastWidget {{
                background-color: #2c3e50;
                border-left: 5px solid {accent_color};
                border-radius: 5px;
            }}
            QLabel {{ color: white; }}
        """)

        self.setFixedSize(300, 70)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 10, 10)

        # Текстовая часть
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        text_layout.addWidget(lbl_title)

        lbl_msg = QLabel(message)
        lbl_msg.setFont(QFont("Arial", 9))
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet("color: #bdc3c7;")
        text_layout.addWidget(lbl_msg)

        layout.addLayout(text_layout)
        layout.addStretch()

        # Кнопка закрытия
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton { background: none; color: #7f8c8d; border: none; font-weight: bold; }
            QPushButton:hover { color: white; }
        """)
        btn_close.clicked.connect(self.close_toast)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignTop)

        # Таймер авто-закрытия (4 секунды)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.close_toast)
        self.timer.start(4000)

        # Эффект прозрачности для анимации
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        # Анимация появления (Fade In + Slide Up)
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.start()

    def close_toast(self):
        # Анимация исчезновения
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(1)
        self.anim.setEndValue(0)
        self.anim.finished.connect(self.close)  # Удалить виджет после анимации
        self.anim.start()

    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)


class NotificationManager:
    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.active_toasts = []

    def show(self, title, message, type_name="info"):
        toast = ToastNotification(self.parent, title, message, type_name)
        toast.show()

        # Добавляем в список и пересчитываем позиции
        self.active_toasts.append(toast)
        self.reposition_toasts()

        # Когда тост удалится, убираем из списка
        toast.destroyed.connect(lambda: self.remove_toast(toast))

    def remove_toast(self, toast):
        if toast in self.active_toasts:
            self.active_toasts.remove(toast)
            self.reposition_toasts()

    def reposition_toasts(self):
        # Позиционируем справа сверху
        margin_x = 20
        margin_y = 50  # Отступ сверху
        spacing = 10

        parent_w = self.parent.width()

        y_offset = margin_y
        for toast in self.active_toasts:
            x = parent_w - toast.width() - margin_x

            # Анимируем перемещение (если тост выше удалился)
            toast.move(x, y_offset)
            y_offset += toast.height() + spacing