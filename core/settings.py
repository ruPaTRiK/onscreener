import json
import os
import sys

APP_NAME = "onscreener"

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "volume": 0.5,
    "mute": False,
    "window_opacity": 1.0, # Непрозрачность (1.0 = полностью видно)
    "ui_scale": 1.0,
    "theme": "dark"
}

class SettingsManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance.data = DEFAULT_SETTINGS.copy()
            cls._instance.file_path = cls._instance._get_settings_path()
            cls._instance.load()
        return cls._instance

    def _get_settings_path(self):
        """Определяет системную папку для хранения настроек"""
        try:
            if sys.platform == "win32":
                # Windows: C:\Users\User\AppData\Roaming
                base_path = os.getenv('APPDATA')
            elif sys.platform == "darwin":
                # MacOS: ~/Library/Application Support
                base_path = os.path.expanduser("~/Library/Application Support")
            else:
                # Linux: ~/.config
                base_path = os.path.expanduser("~/.config")

            # Полный путь к папке приложения
            app_dir = os.path.join(base_path, APP_NAME)

            # Если папки нет - создаем её
            if not os.path.exists(app_dir):
                os.makedirs(app_dir)

            return os.path.join(app_dir, "settings.json")

        except Exception as e:
            # Если что-то пошло не так (нет прав и т.д.), сохраняем рядом с exe как запасной вариант
            print(f"Не удалось получить системный путь: {e}")
            return "settings.json"

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    loaded = json.load(f)
                    # Обновляем, сохраняя ключи по умолчанию, если их нет в файле
                    for k, v in loaded.items():
                        self.data[k] = v
            except:
                print("Ошибка чтения настроек, сброс.")

    def save(self):
        try:
            with open(self.file_path, "w") as f:
                json.dump(self.data, f, indent=4)
        except:
            print("Ошибка сохранения настроек.")

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()