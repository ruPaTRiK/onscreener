import sys
import os
import subprocess
import urllib.request
import ssl
import shutil
import tempfile


class AutoUpdater:
    def __init__(self, current_version):
        self.current_version = current_version
        # Скачиваем во временную папку системы, чтобы не мусорить рядом с exe
        self.temp_dir = tempfile.gettempdir()
        self.new_exe_name = os.path.join(self.temp_dir, "update_temp.exe")

    def is_update_available(self, remote_version):
        return str(remote_version) > str(self.current_version)

    def download_update(self, url, progress_callback=None):
        try:
            print(f"DEBUG: Скачивание {url} в {self.new_exe_name}")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )

            with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                total_size = int(response.info().get('Content-Length', 0))
                downloaded = 0
                block_size = 8192

                with open(self.new_exe_name, "wb") as f:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer: break
                        downloaded += len(buffer)
                        f.write(buffer)
                        if progress_callback and total_size > 0:
                            percent = int(downloaded * 100 / total_size)
                            progress_callback(percent)
            return True
        except Exception as e:
            print(f"Update error: {e}")
            return False

    def get_resource_path(self, relative_path):
        """Находит updater.exe внутри упакованного приложения"""
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def restart_and_replace(self):
        # 1. Определяем пути
        current_exe = os.path.abspath(sys.executable)
        pid = os.getpid()

        # 2. Достаем updater.exe из ресурсов
        bundled_updater = self.get_resource_path(os.path.join("assets", "updater.exe"))
        extracted_updater = os.path.join(self.temp_dir, "updater_tool.exe")

        try:
            shutil.copy2(bundled_updater, extracted_updater)
        except Exception as e:
            print(f"Ошибка извлечения апдейтера: {e}")
            # Если не вышло (например, запускаем из IDE), попробуем найти рядом
            if os.path.exists("assets/updater.exe"):
                extracted_updater = os.path.abspath("assets/updater.exe")
            else:
                return  # Нечего запускать

        # 3. Запускаем updater.exe
        # Аргументы: [PID, Куда_ставить, Откуда_брать]
        args = [extracted_updater, str(pid), current_exe, self.new_exe_name]

        print(f"Запуск апдейтера: {args}")
        subprocess.Popen(args)

        # 4. Выходим
        os._exit(0)