import json
import os

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
            cls._instance.load()
        return cls._instance

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    loaded = json.load(f)
                    # Обновляем, сохраняя ключи по умолчанию, если их нет в файле
                    for k, v in loaded.items():
                        self.data[k] = v
            except:
                print("Ошибка чтения настроек, сброс.")

    def save(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.data, f, indent=4)
        except:
            print("Ошибка сохранения настроек.")

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()