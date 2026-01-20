#!/usr/bin/env python3
import asyncio
import json
import uuid
import random

HOST = '0.0.0.0'
PORT = 5555


# --- СТРУКТУРЫ ДАННЫХ ---

class Lobby:
    def __init__(self, lobby_id, name, host_writer, is_private=False, password=""):
        self.id = lobby_id
        self.name = name
        self.host = host_writer  # Используем writer как идентификатор соединения
        self.is_private = is_private
        self.password = password
        self.selected_game_id = None
        self.game_started = False

        # {writer: {"name": "...", "ready": False, "id": 1}}
        self.players = {}

    def add_player(self, writer, name):
        pid = 1 if writer == self.host else len(self.players) + 1
        self.players[writer] = {
            "name": name,
            "ready": False,
            "id": pid,
            "writer": writer
        }

    def remove_player(self, writer):
        if writer in self.players:
            del self.players[writer]
        return len(self.players) == 0 or writer == self.host

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "private": self.is_private,
            "players": len(self.players),
            "max": 2
        }

    def get_full_state(self):
        pl_list = []
        for w, p in self.players.items():
            pl_list.append({
                "name": p["name"],
                "ready": p["ready"],
                "is_host": (w == self.host),
                "id": p["id"]
            })
        return {
            "type": "lobby_state",
            "lobby_id": self.id,
            "name": self.name,
            "selected_game": self.selected_game_id,
            "players": pl_list,
            "am_i_host": False
        }


# Глобальные переменные
lobbies = {}  # {lobby_id: Lobby}
clients = {}  # {writer: {"name": "...", "current_lobby": id}}


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def send_json(writer, data):
    """Асинхронная отправка JSON"""
    try:
        if writer.is_closing(): return
        msg = json.dumps(data) + "\n"
        writer.write(msg.encode('utf-8'))
        await writer.drain()  # Ждем, пока данные уйдут в буфер
    except Exception:
        pass


async def broadcast_lobby_list():
    """Рассылает список комнат всем свободным игрокам"""
    lobby_list = [l.to_dict() for l in lobbies.values() if not l.game_started]
    msg = {"type": "lobby_list", "lobbies": lobby_list}

    for writer, data in clients.items():
        if data["current_lobby"] is None:
            await send_json(writer, msg)


async def broadcast_lobby_state(lobby):
    """Рассылает состояние внутри комнаты"""
    base_state = lobby.get_full_state()
    for writer in lobby.players:
        state = base_state.copy()
        state["am_i_host"] = (writer == lobby.host)
        await send_json(writer, state)


async def leave_current_lobby(writer):
    """Логика выхода из лобби"""
    if writer not in clients: return
    lid = clients[writer]["current_lobby"]

    if lid and lid in lobbies:
        lobby = lobbies[lid]
        should_close = lobby.remove_player(writer)
        clients[writer]["current_lobby"] = None

        if should_close:
            del lobbies[lid]
            # Выкидываем остальных, если хост ушел
            for w in list(lobby.players.keys()):
                clients[w]["current_lobby"] = None
                await send_json(w, {"type": "kicked", "msg": "Хост покинул лобби"})
                # Удаляем из списка игроков, чтобы цикл не сломался
                if w in lobby.players: del lobby.players[w]
        else:
            await broadcast_lobby_state(lobby)

        await broadcast_lobby_list()
        await send_json(writer, {"type": "left_lobby_success"})


async def start_game_sequence(lobby):
    """Запуск процедуры начала игры (Монетка)"""
    lobby.game_started = True
    await broadcast_lobby_list()

    players = list(lobby.players.keys())
    if len(players) < 2: return  # Защита

    picker = random.choice(players)
    waiter = players[0] if players[1] == picker else players[1]

    await send_json(picker, {"type": "match_found", "role": "picker"})
    await send_json(waiter, {"type": "match_found", "role": "waiter"})


async def pass_to_opponent(sender_writer, lobby, data):
    """Пересылка данных сопернику"""
    for w in lobby.players:
        if w != sender_writer:
            await send_json(w, data)


# --- ОСНОВНАЯ ЛОГИКА ---

async def handle_client(reader, writer):
    """Обработчик одного подключения"""
    addr = writer.get_extra_info('peername')
    print(f"Подключился: {addr}")

    try:
        while True:
            # Читаем строку (клиент должен слать \n в конце каждого JSON)
            raw_data = await reader.readline()
            if not raw_data: break  # Соединение разорвано

            try:
                data = json.loads(raw_data.decode('utf-8'))
            except json.JSONDecodeError:
                continue

            ctype = data.get("type")

            # 1. ЛОГИН
            if ctype == "login":
                clients[writer] = {"name": data["name"], "current_lobby": None}
                await broadcast_lobby_list()

            # 2. СОЗДАТЬ ЛОББИ
            elif ctype == "create_lobby":
                lid = str(uuid.uuid4())[:8]
                name = data.get("name", "Room")
                is_private = data.get("is_private", False)
                pwd = data.get("password", "")

                new_lobby = Lobby(lid, name, writer, is_private, pwd)
                new_lobby.add_player(writer, clients[writer]["name"])

                lobbies[lid] = new_lobby
                clients[writer]["current_lobby"] = lid

                await broadcast_lobby_list()
                await broadcast_lobby_state(new_lobby)

            # 3. ВОЙТИ В ЛОББИ
            elif ctype == "join_lobby":
                lid = data["lobby_id"]
                pwd = data.get("password", "")

                if lid in lobbies:
                    lobby = lobbies[lid]
                    if len(lobby.players) >= 2:
                        await send_json(writer, {"type": "error", "msg": "Комната полна"})
                    elif lobby.is_private and lobby.password != pwd:
                        await send_json(writer, {"type": "error", "msg": "Неверный пароль"})
                    else:
                        lobby.add_player(writer, clients[writer]["name"])
                        clients[writer]["current_lobby"] = lid
                        await broadcast_lobby_state(lobby)
                        await broadcast_lobby_list()

            # 4. ВЫЙТИ
            elif ctype == "leave_lobby":
                await leave_current_lobby(writer)

            # 5. ВЫБОР ИГРЫ
            elif ctype == "select_game":
                lid = clients[writer]["current_lobby"]
                if lid and lid in lobbies:
                    lobby = lobbies[lid]
                    if writer == lobby.host:
                        lobby.selected_game_id = data["game_id"]
                        for p in lobby.players.values(): p["ready"] = False
                        await broadcast_lobby_state(lobby)

            # 6. ГОТОВНОСТЬ
            elif ctype == "toggle_ready":
                lid = clients[writer]["current_lobby"]
                if lid and lid in lobbies:
                    lobby = lobbies[lid]
                    lobby.players[writer]["ready"] = data["status"]
                    await broadcast_lobby_state(lobby)

                    all_ready = all(p["ready"] for p in lobby.players.values())
                    if all_ready and len(lobby.players) == 2 and lobby.selected_game_id:
                        await start_game_sequence(lobby)

            # 7. МОНЕТКА
            elif ctype == "coin_choice":
                lid = clients[writer]["current_lobby"]
                if lid and lid in lobbies:
                    lobby = lobbies[lid]
                    choice = data["choice"]
                    result = random.choice(["heads", "tails"])
                    is_winner = (choice == result)

                    # Находим соперника
                    opponent = next((w for w in lobby.players if w != writer), None)

                    await send_json(writer, {"type": "coin_result", "result": result, "win": is_winner})
                    if opponent:
                        await send_json(opponent, {"type": "coin_result", "result": result, "win": not is_winner})

            # 8. ВЫБОР ПОРЯДКА (СТАРТ)
            elif ctype == "order_choice":
                lid = clients[writer]["current_lobby"]
                if lid and lid in lobbies:
                    lobby = lobbies[lid]
                    choice = data["choice"]

                    if choice == "first":
                        h_col, g_col = "white", "black"
                    else:
                        h_col, g_col = "black", "white"

                    opponent = next((w for w in lobby.players if w != writer), None)
                    game_id = lobby.selected_game_id

                    await send_json(writer, {"type": "start_game", "game": game_id, "color": h_col})
                    if opponent:
                        await send_json(opponent, {"type": "start_game", "game": game_id, "color": g_col})

                    lobby.game_started = True
                    await broadcast_lobby_list()

            # 9. ИГРА (Ходы)
            elif ctype in ["game_move", "game_emote"]:
                lid = clients[writer]["current_lobby"]
                if lid and lid in lobbies:
                    await pass_to_opponent(writer, lobbies[lid], data)

            # 10. РЕСТАРТ (МЯГКАЯ СМЕНА СТОРОН)
            elif ctype == "restart_game":
                lid = clients[writer]["current_lobby"]
                if lid and lid in lobbies:
                    lobby = lobbies[lid]
                    players = list(lobby.players.keys())

                    if len(players) < 2:
                        # Если один - просто сброс
                        for w in lobby.players:
                            await send_json(w, {"type": "restart_cmd"})
                    else:
                        # Смена сторон
                        if not hasattr(lobby, "current_first_index"):
                            lobby.current_first_index = 0

                        lobby.current_first_index = 1 - lobby.current_first_index
                        new_first_writer = players[lobby.current_first_index]

                        for w in players:
                            color = "white" if w == new_first_writer else "black"
                            # Шлем новую команду restart_swap
                            await send_json(w, {"type": "restart_swap", "color": color})

            # ЧАТ В ЛОББИ
            elif ctype == "chat_msg":
                lid = clients[writer]["current_lobby"]
                if lid and lid in lobbies:
                    lobby = lobbies[lid]
                    sender_name = clients[writer]["name"]
                    msg_text = data.get("text", "")

                    # Формируем пакет для рассылки
                    payload = {
                        "type": "chat_msg",
                        "sender": sender_name,
                        "text": msg_text
                    }

                    for w in lobby.players:
                        if w != writer:
                            await send_json(w, payload)

    except Exception as e:
        print(f"Connection error with {addr}: {e}")
    finally:
        print(f"Отключился: {addr}")
        await leave_current_lobby(writer)
        if writer in clients: del clients[writer]
        writer.close()
        await writer.wait_closed()


async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    addr = server.sockets[0].getsockname()
    print(f'Server serving on {addr} (AsyncIO)')

    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nСервер остановлен.")