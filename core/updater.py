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
        # Простое сравнение строк или чисел
        # Если 1.1 > 1.0
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
        import sys
        import os
        import subprocess

        current_exe = os.path.abspath(sys.executable)  # АБСОЛЮТНЫЙ путь
        exe_dir = os.path.dirname(current_exe)
        exe_name = os.path.basename(current_exe)
        new_exe_path = os.path.abspath(self.new_exe_name)  # АБСОЛЮТНЫЙ путь
        pid = os.getpid()

        bat_script = f'''@echo off
        cd /d "{exe_dir}"

        REM Ждём смерти процесса
        :loop
        tasklist /FI "PID eq {pid}" 2^>NUL | find /I /N "{pid}" >NUL
        if "%ERRORLEVEL%"=="0" (
            timeout /t 2 /nobreak >NUL
            goto loop
        )

        REM Длинная пауза - даём системе полностью освободить файлы (критично!)
        timeout /t 5 /nobreak >NUL

        REM Очищаем ВСЕ старые _MEI папки этого пользователя (профилактика)
        for /d %%i in ("%TEMP%\*MEI*") do rd /s /q "%%i" 2>nul

        REM Ещё пауза для нового TEMP
        timeout /t 3 /nobreak >NUL

        REM Теперь заменяем
        :try_move
        move /Y "{new_exe_path}" "{current_exe}" >NUL 2>&1
        if errorlevel 1 (
            timeout /t 2 /nobreak >NUL
            goto try_move
        )

        REM Запускаем
        start "" "{current_exe}"
        del "%~f0"
        '''

        with open(self.bat_name, "w", encoding='utf-8') as f:
            f.write(bat_script)

        # Запускаем с явной рабочей директорией
        subprocess.Popen([self.bat_name], cwd=exe_dir, shell=True)
        os._exit(0)