import sys
import os
import time
import subprocess
import shutil


def is_pid_running(pid):
    """Проверяет, жив ли процесс"""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        SYNCHRONIZE = 0x00100000
        process = kernel32.OpenProcess(SYNCHRONIZE, 0, pid)
        if process != 0:
            kernel32.CloseHandle(process)
            return True
        return False
    except:
        return False


def main():
    # Аргументы: [script_name, pid_to_wait, current_exe, new_exe]
    if len(sys.argv) < 4:
        return

    try:
        pid = int(sys.argv[1])
        target_exe = sys.argv[2]  # Куда ставить (текущая игра)
        source_exe = sys.argv[3]  # Откуда брать (скачанный файл)

        # 1. Ждем завершения основного процесса
        print(f"Waiting for PID {pid}...")
        attempts = 0
        while is_pid_running(pid) and attempts < 10:
            time.sleep(1)
            attempts += 1

        # На всякий случай еще пауза
        time.sleep(1)

        # 2. Перемещаем файл (Замена)
        print(f"Replacing {target_exe}...")
        for _ in range(10):  # 10 попыток
            try:
                shutil.move(source_exe, target_exe)
                break
            except OSError:
                time.sleep(1)

        # 3. Запускаем обновленную игру
        print("Launching...")
        subprocess.Popen([target_exe])

    except Exception as e:
        # Если что-то пошло не так, можно записать лог в файл рядом
        with open("update_error.log", "w") as f:
            f.write(str(e))


if __name__ == "__main__":
    main()