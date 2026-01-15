import os
import sys
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtCore import QUrl


class SoundManager:
    _instance = None  # Singleton

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SoundManager, cls).__new__(cls)
            cls._instance.sounds = {}
            cls._instance.muted = False
            cls._instance.volume = 0.5  # 0.0 to 1.0
            cls._instance.load_sounds()
        return cls._instance

    def resource_path(self, relative_path):
        """Получает путь к ресурсам внутри EXE или в папке проекта"""
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def load_sounds(self):
        # Список звуков и путей (относительно assets/sounds/)
        sound_files = {
            "click": "click.wav",  # Клик по кнопке
            "move": "move.wav",  # Ход в шашках/шахматах
            # "capture": "capture.wav",  # Взятие фигуры
            # "win": "win.wav",  # Победа
            # "lose": "lose.wav",  # Поражение
            "notification": "notify.wav",  # Уведомление в лаунчере
            "shot": "shot.wav",  # Выстрел (Морской бой)
            "miss": "miss.wav",  # Промах (Морской бой)
            "boom": "shipExplode.wav"  # Попадание (Морской бой)
        }

        for name, filename in sound_files.items():
            full_path = self.resource_path(os.path.join("assets", "sounds", filename))

            if os.path.exists(full_path):
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(full_path))
                effect.setVolume(self.volume)
                self.sounds[name] = effect
            else:
                print(f"Звук не найден: {filename}")

    def play(self, name):
        if self.muted: return
        if name in self.sounds:
            # Если звук уже играет, остановить и запустить заново (для быстрых кликов)
            if self.sounds[name].isPlaying():
                self.sounds[name].stop()
            self.sounds[name].play()

    def set_volume(self, vol):
        """vol: 0.0 to 1.0"""
        self.volume = vol
        for effect in self.sounds.values():
            effect.setVolume(vol)

    def toggle_mute(self):
        self.muted = not self.muted