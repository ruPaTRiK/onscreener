import sys
import os
import urllib.request
import subprocess
import ssl


class AutoUpdater:
    def __init__(self, current_version):
        self.current_version = current_version
        self.new_exe_name = "update_temp.exe"
        self.bat_name = "update_script.bat"

    def is_update_available(self, remote_version):
        return str(remote_version) > str(self.current_version)

    def download_update(self, url, progress_callback=None):
        try:
            # Игнор SSL (как в лаунчере)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # Скачиваем во временный файл
            with urllib.request.urlopen(url, context=ctx) as response:
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
            print(f"Ошибка обновления: {e}")
            return False

    def restart_and_replace(self):
        """
        Создает BAT-файл, который:
        1. Ждет закрытия нашей программы.
        2. Удаляет старый exe.
        3. Переименовывает новый exe в старое имя.
        4. Запускает его.
        5. Удаляет себя.
        """
        current_exe = sys.executable
        exe_name = os.path.basename(current_exe)

        # Скрипт обновления (Windows Batch)
        bat_script = f"""
@echo off
timeout /t 2 /nobreak > NUL
del "{exe_name}"
move "{self.new_exe_name}" "{exe_name}"
start "" "{exe_name}"
del "{self.bat_name}"
        """

        with open(self.bat_name, "w") as f:
            f.write(bat_script)

        # Запускаем BAT и закрываемся
        subprocess.Popen([self.bat_name], shell=True)
        sys.exit(0)