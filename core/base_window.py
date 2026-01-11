from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtCore import Qt, QPoint, QRect


class OverlayWindow(QMainWindow):
    def __init__(self, overlay_mode=True):
        super().__init__()

        self._action = None
        self._start_pos = QPoint()
        self._start_frame = QRect()
        self._aspect_ratio = 1.0

        # Минимальный размер, чтобы окно не схлопнулось в 0
        self.setMinimumSize(200, 200)

        # Базовый флаг - без рамок
        flags = Qt.WindowType.FramelessWindowHint

        if overlay_mode:
            # Для игр: Поверх окон, нет в панели задач
            flags |= Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        else:
            # Для лаунчера: Обычное поведение (сворачивается, есть в панели)
            pass

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def mousePressEvent(self, event):
        modifiers = QApplication.keyboardModifiers()

        if modifiers == Qt.KeyboardModifier.ShiftModifier:
            self._start_pos = event.globalPosition().toPoint()
            self._start_frame = self.frameGeometry()

            if event.button() == Qt.MouseButton.LeftButton:
                self._action = 'move'
                event.accept()
                return

            elif event.button() == Qt.MouseButton.RightButton:
                self._action = 'resize'
                w = self._start_frame.width()
                h = self._start_frame.height()
                self._aspect_ratio = w / h if h > 0 else 1.0
                event.accept()
                return

        self._action = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._action is None:
            super().mouseMoveEvent(event)
            return

        current_pos = event.globalPosition().toPoint()
        delta = current_pos - self._start_pos

        if self._action == 'move':
            new_pos = self._start_frame.topLeft() + delta
            self.move(new_pos)

        elif self._action == 'resize':
            # Логика изменения размера
            # Мы берем большую дельту, чтобы движение было плавным
            # Если тянем влево (отрицательная delta), размер уменьшается

            change = 0
            if abs(delta.x()) > abs(delta.y()):
                change = delta.x()
                new_width = self._start_frame.width() + change
                new_height = int(new_width / self._aspect_ratio)
            else:
                change = delta.y()
                new_height = self._start_frame.height() + change
                new_width = int(new_height * self._aspect_ratio)

            # Применяем ограничения min/max вручную, чтобы не ломать пропорции
            if new_width >= 200 and new_height >= 200:
                self.resize(new_width, new_height)

    def mouseReleaseEvent(self, event):
        self._action = None
        super().mouseReleaseEvent(event)