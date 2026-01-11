#!/usr/bin/env python3
import socket
import threading
import json
import uuid

HOST = '0.0.0.0'
PORT = 5555


# Структуры данных
class Lobby:
    def __init__(self, lobby_id, name, host_sock, is_private=False, password=""):
        self.id = lobby_id
        self.name = name
        self.host = host_sock  # Сокет создателя
        self.is_private = is_private
        self.password = password
        self.selected_game_id = None
        self.game_started = False

        # Игроки в комнате: {socket: {"name": "...", "ready": False, "id": 1}}
        self.players = {}

    def add_player(self, sock, name):
        # Генерируем временный ID (1 или 2, или uuid)
        # Для простоты: 1 - хост, 2 - гость
        pid = 1 if sock == self.host else len(self.players) + 1
        self.players[sock] = {
            "name": name,
            "ready": False,
            "id": pid,
            "sock": sock
        }

    def remove_player(self, sock):
        if sock in self.players:
            del self.players[sock]
        # Если ушел хост - комната удаляется (в простой реализации)
        return len(self.players) == 0 or sock == self.host

    def to_dict(self):
        """Инфо для списка лобби"""
        return {
            "id": self.id,
            "name": self.name,
            "private": self.is_private,
            "players": len(self.players),
            "max": 2  # Пока ограничим 2 игроками
        }

    def get_full_state(self):
        """Полное состояние для тех, кто внутри"""
        pl_list = []
        for s, p in self.players.items():
            pl_list.append({
                "name": p["name"],
                "ready": p["ready"],
                "is_host": (s == self.host),
                "id": p["id"]
            })
        return {
            "type": "lobby_state",
            "lobby_id": self.id,
            "name": self.name,
            "selected_game": self.selected_game_id,
            "players": pl_list,
            "am_i_host": False  # Заполняется индивидуально при отправке
        }


lobbies = {}  # {lobby_id: Lobby}
clients = {}  # {socket: {"name": "...", "current_lobby": id}}

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def send_json(sock, data):
    try:
        msg = json.dumps(data) + "\n"
        sock.send(msg.encode('utf-8'))
    except:
        pass


def broadcast_lobby_list():
    """Рассылает список комнат всем, кто НЕ в игре"""
    lobby_list = [l.to_dict() for l in lobbies.values() if not l.game_started]
    msg = {"type": "lobby_list", "lobbies": lobby_list}

    for sock, data in clients.items():
        if data["current_lobby"] is None:
            send_json(sock, msg)


def broadcast_lobby_state(lobby):
    """Рассылает состояние комнаты тем, кто внутри"""
    base_state = lobby.get_full_state()
    for sock in lobby.players:
        # Для каждого игрока помечаем, хост он или нет
        state = base_state.copy()
        state["am_i_host"] = (sock == lobby.host)
        send_json(sock, state)


# --- ЛОГИКА ---
def handle_client(sock):
    try:
        while True:
            raw = sock.recv(4096)
            if not raw: break
            parts = raw.decode('utf-8').split('\n')

            for part in parts:
                if not part.strip(): continue
                data = json.loads(part)
                ctype = data.get("type")

                # 1. АВТОРИЗАЦИЯ (Просто имя)
                if ctype == "login":
                    clients[sock] = {"name": data["name"], "current_lobby": None}
                    broadcast_lobby_list()  # Шлем список комнат

                # 2. СОЗДАНИЕ ЛОББИ
                elif ctype == "create_lobby":
                    lid = str(uuid.uuid4())[:8]
                    name = data.get("name", "Room")
                    is_private = data.get("is_private", False)
                    pwd = data.get("password", "")

                    new_lobby = Lobby(lid, name, sock, is_private, pwd)
                    new_lobby.add_player(sock, clients[sock]["name"])

                    lobbies[lid] = new_lobby
                    clients[sock]["current_lobby"] = lid

                    broadcast_lobby_list()  # Обновляем список у других
                    broadcast_lobby_state(new_lobby)  # Показываем комнату создателю

                # 3. ВХОД В ЛОББИ
                elif ctype == "join_lobby":
                    lid = data["lobby_id"]
                    pwd = data.get("password", "")

                    if lid in lobbies:
                        lobby = lobbies[lid]
                        if len(lobby.players) >= 2:
                            send_json(sock, {"type": "error", "msg": "Комната полна"})
                        elif lobby.is_private and lobby.password != pwd:
                            send_json(sock, {"type": "error", "msg": "Неверный пароль"})
                        else:
                            lobby.add_player(sock, clients[sock]["name"])
                            clients[sock]["current_lobby"] = lid
                            broadcast_lobby_state(lobby)
                            broadcast_lobby_list()

                # 4. ВЫХОД ИЗ ЛОББИ
                elif ctype == "leave_lobby":
                    leave_current_lobby(sock)

                # 5. ВЫБОР ИГРЫ (Только хост)
                elif ctype == "select_game":
                    lid = clients[sock]["current_lobby"]
                    if lid and lid in lobbies:
                        lobby = lobbies[lid]
                        if sock == lobby.host:
                            lobby.selected_game_id = data["game_id"]
                            # Сбрасываем готовность при смене игры
                            for p in lobby.players.values(): p["ready"] = False
                            broadcast_lobby_state(lobby)

                # 6. ГОТОВНОСТЬ
                elif ctype == "toggle_ready":
                    lid = clients[sock]["current_lobby"]
                    if lid and lid in lobbies:
                        lobby = lobbies[lid]
                        lobby.players[sock]["ready"] = data["status"]
                        broadcast_lobby_state(lobby)

                        # ПРОВЕРКА СТАРТА (Все готовы + выбрана игра + 2 игрока)
                        all_ready = all(p["ready"] for p in lobby.players.values())
                        if all_ready and len(lobby.players) == 2 and lobby.selected_game_id:
                            start_game_sequence(lobby)

                    # 7. БРОСОК МОНЕТКИ
                elif ctype == "coin_choice":
                    lid = clients[sock]["current_lobby"]
                    if lid and lid in lobbies:
                        lobby = lobbies[lid]

                        choice = data["choice"]  # "heads" или "tails"

                        # Сервер бросает монетку
                        import random
                        result = random.choice(["heads", "tails"])

                        # Определяем победителя
                        # sock - это тот, кто выбирал (picker)
                        # Его выбор совпал с результатом?
                        is_winner = (choice == result)

                        # Находим соперника
                        opponent = None
                        for s in lobby.players:
                            if s != sock: opponent = s

                        # Отправляем результаты обоим
                        # Тот, кто выбирал:
                        send_json(sock, {"type": "coin_result", "result": result, "win": is_winner})
                        # Тот, кто ждал (opponent):
                        # Если выбирающий победил, значит ждущий проиграл
                        if opponent:
                            send_json(opponent, {"type": "coin_result", "result": result, "win": not is_winner})

                # 8. ВЫБОР ПОРЯДКА ХОДА (После победы в монетке)
                elif ctype == "order_choice":
                    lid = clients[sock]["current_lobby"]
                    if lid and lid in lobbies:
                        lobby = lobbies[lid]
                        choice = data["choice"]  # "first" или "second"

                        # Тот, кто выбирал порядок, играет за:
                        if choice == "first":
                            host_color = "white"  # Тот, кто выбирал
                            guest_color = "black"
                        else:
                            host_color = "black"
                            guest_color = "white"

                        # sock - это победитель монетки. Определяем соперника.
                        opponent = None
                        for s in lobby.players:
                            if s != sock: opponent = s

                        game_id = lobby.selected_game_id

                        # Запускаем игру!
                        send_json(sock, {"type": "start_game", "game": game_id, "color": host_color})
                        if opponent:
                            send_json(opponent, {"type": "start_game", "game": game_id, "color": guest_color})

                        lobby.game_started = True
                        broadcast_lobby_list()  # Убираем лобби из списка доступных

                # 9. ОБЫЧНАЯ ПЕРЕСЫЛКА ХОДОВ
                elif ctype == "game_move":
                    lid = clients[sock]["current_lobby"]
                    if lid and lid in lobbies:
                        pass_to_opponent(sock, lobbies[lid], data)

                # 10. РЕСТАРТ ИГРЫ (Исправлено)
                elif ctype == "restart_game":
                    lid = clients[sock]["current_lobby"]
                    if lid and lid in lobbies:
                        lobby = lobbies[lid]
                        # Отправляем команду сброса ВСЕМ игрокам в комнате (и себе, и сопернику)
                        msg = {"type": "restart_cmd"}
                        for s in lobby.players:
                            send_json(s, msg)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        leave_current_lobby(sock)
        if sock in clients: del clients[sock]
        sock.close()


def leave_current_lobby(sock):
    if sock not in clients: return
    lid = clients[sock]["current_lobby"]
    if lid and lid in lobbies:
        lobby = lobbies[lid]
        should_close = lobby.remove_player(sock)
        clients[sock]["current_lobby"] = None

        if should_close:
            del lobbies[lid]
            # Выкидываем остальных (если хост вышел)
            for s in list(lobby.players.keys()):
                clients[s]["current_lobby"] = None
                send_json(s, {"type": "kicked", "msg": "Хост покинул лобби"})
                lobby.remove_player(s)  # Чтобы цикл не сломался
        else:
            broadcast_lobby_state(lobby)

        broadcast_lobby_list()
        send_json(sock, {"type": "left_lobby_success"})


def start_game_sequence(lobby):
    lobby.game_started = True
    broadcast_lobby_list()  # Убираем из списка доступных

    # Запускаем монетку
    import random
    players = list(lobby.players.keys())
    picker = random.choice(players)
    waiter = players[0] if players[1] == picker else players[1]

    send_json(picker, {"type": "match_found", "role": "picker"})
    send_json(waiter, {"type": "match_found", "role": "waiter"})


def pass_to_opponent(sender, lobby, data):
    # Находим соперника в комнате
    for sock in lobby.players:
        if sock != sender:
            send_json(sock, data)


print("Сервер лобби запущен (Ctrl+C для остановки)...")

# 1. Устанавливаем таймаут 1 секунду
# Это заставляет server.accept() выбрасывать ошибку socket.timeout каждую секунду,
# если никто не подключился. Это дает циклу шанс проверить Ctrl+C.
server.settimeout(1.0)

try:
    while True:
        try:
            conn, addr = server.accept()

            # 2. Делаем поток фоновым (daemon=True)
            # Это значит, что если главный скрипт закроется, этот поток умрет сам.
            t = threading.Thread(target=handle_client, args=(conn,), daemon=True)
            t.start()

        except socket.timeout:
            # Никто не подключился за последнюю секунду - идем на новый круг цикла
            continue

except KeyboardInterrupt:
    print("\nОстановка сервера...")
finally:
    server.close()
    print("Сервер остановлен.")