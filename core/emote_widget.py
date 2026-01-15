from PyQt6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QParallelAnimationGroup


class FloatingEmote(QLabel):
    def __init__(self, parent, text, start_pos):
        super().__init__(parent)
        self.setText(text)
        self.setFont(parent.font())  # Можно задать свой шрифт побольше
        # Стиль эмодзи (большой, с тенью)
        self.setStyleSheet("font-size: 64px; color: white; background: transparent;")
        self.adjustSize()

        # Центрируем относительно start_pos
        self.move(start_pos.x() - self.width() // 2, start_pos.y() - self.height() // 2)
        self.show()

        # Эффект прозрачности
        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)

        # Анимация Движения (вверх)
        self.anim_pos = QPropertyAnimation(self, b"pos")
        self.anim_pos.setDuration(1500)
        self.anim_pos.setStartValue(self.pos())
        self.anim_pos.setEndValue(QPoint(self.pos().x(), self.pos().y() - 100))
        self.anim_pos.setEasingCurve(QEasingCurve.Type.OutQuad)

        # Анимация Исчезновения
        self.anim_fade = QPropertyAnimation(self.opacity, b"opacity")
        self.anim_fade.setDuration(1500)
        self.anim_fade.setStartValue(1.0)
        self.anim_fade.setEndValue(0.0)
        self.anim_fade.setEasingCurve(QEasingCurve.Type.InQuad)

        # Группа (запускаем вместе)
        self.group = QParallelAnimationGroup()
        self.group.addAnimation(self.anim_pos)
        self.group.addAnimation(self.anim_fade)
        self.group.finished.connect(self.deleteLater)
        self.group.start()