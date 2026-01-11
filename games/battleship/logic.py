class BattleshipLogic:
    def __init__(self):
        # Конфигурация флота: {id: size}
        # Используем уникальные ID для каждого корабля, чтобы перемещать их
        self.fleet_config = [
            {"id": 1, "size": 4},
            {"id": 2, "size": 3}, {"id": 3, "size": 3},
            {"id": 4, "size": 2}, {"id": 5, "size": 2}, {"id": 6, "size": 2},
            {"id": 7, "size": 1}, {"id": 8, "size": 1}, {"id": 9, "size": 1}, {"id": 10, "size": 1}
        ]
        self.reset_game()

    def reset_game(self):
        # 0-пусто, id-корабль
        self.my_board = [[0] * 10 for _ in range(10)]
        self.enemy_view = [[0] * 10 for _ in range(10)]

        self.placed_ships = {}

        self.total_health = sum(ship["size"] for ship in self.fleet_config)
        print(f"DEBUG: Игра началась. Всего жизней: {self.total_health}")

        self.my_hits_taken = 0
        self.enemy_hits_made = 0

        self.phase = 'setup'
        self.my_turn = False
        self.game_over = False
        self.winner = None

    def is_ship_placed(self, ship_id):
        return ship_id in self.placed_ships

    def remove_ship(self, ship_id):
        if ship_id in self.placed_ships:
            data = self.placed_ships[ship_id]
            # Очищаем клетки на доске
            for i in range(data["size"]):
                if data["ori"] == 'h':
                    self.my_board[data["r"]][data["c"] + i] = 0
                else:
                    self.my_board[data["r"] + i][data["c"]] = 0
            del self.placed_ships[ship_id]

    def place_ship(self, ship_id, r, c, orientation):
        # Сначала найдем размер
        size = next((s["size"] for s in self.fleet_config if s["id"] == ship_id), 0)
        if size == 0: return False

        # Если корабль уже стоял - временно убираем его, чтобы проверить новое место
        # (вдруг мы его просто сдвигаем на 1 клетку)
        old_data = None
        if ship_id in self.placed_ships:
            old_data = self.placed_ships[ship_id]
            self.remove_ship(ship_id)

        if self._can_place(r, c, size, orientation, ignore_id=ship_id):
            # Ставим
            for i in range(size):
                if orientation == 'h':
                    self.my_board[r][c + i] = ship_id
                else:
                    self.my_board[r + i][c] = ship_id

            self.placed_ships[ship_id] = {"r": r, "c": c, "ori": orientation, "size": size}
            return True
        else:
            # Если не смогли поставить - возвращаем на старое место (если было)
            if old_data:
                self.place_ship(ship_id, old_data["r"], old_data["c"], old_data["ori"])
            return False

    def _can_place(self, r, c, size, orientation, ignore_id):
        # 1. Границы
        if orientation == 'h':
            if c + size > 10: return False
        else:
            if r + size > 10: return False

        # 2. Пересечения (вокруг должно быть пусто или занято ЭТИМ ЖЕ кораблем)
        ship_cells = []
        for i in range(size):
            if orientation == 'h':
                ship_cells.append((r, c + i))
            else:
                ship_cells.append((r + i, c))

        for sr, sc in ship_cells:
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = sr + dr, sc + dc
                    if 0 <= nr < 10 and 0 <= nc < 10:
                        cell_val = self.my_board[nr][nc]
                        if cell_val != 0 and cell_val != ignore_id:
                            return False
        return True

    def are_all_placed(self):
        return len(self.placed_ships) == len(self.fleet_config)

    def receive_shot(self, r, c):
        """Обрабатывает выстрел ПРОТИВНИКА по мне"""
        cell = self.my_board[r][c]

        if cell == 0:
            self.my_board[r][c] = -1  # Промах
            self.my_turn = True
            return "miss", None

        elif cell > 0:
            ship_id = cell
            self.my_board[r][c] = -2  # Попадание
            self.my_hits_taken += 1

            print(f"DEBUG: Меня ранили! Урон: {self.my_hits_taken}/{self.total_health}")

            # Проверяем, убит ли корабль целиком
            ship_dead = self._is_ship_dead(ship_id)
            ship_data = None
            status = "hit"

            if ship_dead:
                self._mark_dead_ship(ship_id)
                ship_data = self.placed_ships[ship_id]
                status = "kill"

            # --- ИСПРАВЛЕНИЕ: ПРОВЕРКА ПОБЕДЫ ---
            if self.my_hits_taken >= self.total_health:
                self.game_over = True
                self.winner = 'enemy'  # Победил тот, кто стрелял (враг)

            return status, ship_data

        return "already", None

    def process_shot_result(self, r, c, status, ship_data=None):
        """Записываем результат МОЕГО выстрела на правом поле"""
        if status == "miss":
            self.enemy_view[r][c] = 1
            self.my_turn = False

        elif status == "hit":
            self.enemy_view[r][c] = 2
            self.enemy_hits_made += 1

        elif status == "kill":
            self.enemy_view[r][c] = 2
            self.enemy_hits_made += 1
            if ship_data:
                self._mark_enemy_dead_ship(ship_data)

        if status in ["hit", "kill"]:
            # --- DEBUG PRINT ---
            print(f"DEBUG: Я попал! Мой счет: {self.enemy_hits_made}/{self.total_health}")

            if self.enemy_hits_made >= self.total_health:
                print("DEBUG: Я ПОБЕДИЛ!")
                self.game_over = True
                self.winner = 'me'

    def _is_ship_dead(self, ship_id):
        # Проверяем все клетки этого корабля
        data = self.placed_ships[ship_id]
        size = data["size"]
        hits = 0
        for i in range(size):
            if data["ori"] == 'h':
                if self.my_board[data["r"]][data["c"] + i] == -2: hits += 1
            else:
                if self.my_board[data["r"] + i][data["c"]] == -2: hits += 1

        # ВНИМАНИЕ: Если мы только что попали, клетка уже -2.
        # То есть если hits == size, то убит.
        return hits == size

    def _mark_dead_ship(self, ship_id):
        """Помечаем мой корабль как -3 (убит) и ставим ореол -1 (промахи)"""
        data = self.placed_ships[ship_id]
        r, c, size, ori = data["r"], data["c"], data["size"], data["ori"]

        # 1. Меняем статус палуб на -3
        for i in range(size):
            if ori == 'h':
                self.my_board[r][c + i] = -3
            else:
                self.my_board[r + i][c] = -3

        # 2. Ставим ореол (авто-промахи)
        self._set_halo(self.my_board, r, c, size, ori, mark=-1)

    def _mark_enemy_dead_ship(self, data):
        """Рисуем убитый корабль врага на правом поле"""
        r, c, size, ori = data["r"], data["c"], data["size"], data["ori"]

        # 1. Палубы = 3 (Убит)
        for i in range(size):
            if ori == 'h':
                self.enemy_view[r][c + i] = 3
            else:
                self.enemy_view[r + i][c] = 3

        # 2. Ореол = 1 (Промах)
        self._set_halo(self.enemy_view, r, c, size, ori, mark=1)

    def _set_halo(self, board, r, c, size, ori, mark):
        # Генерируем клетки корабля
        ship_cells = []
        for i in range(size):
            if ori == 'h':
                ship_cells.append((r, c + i))
            else:
                ship_cells.append((r + i, c))

        # Проходим соседей
        for sr, sc in ship_cells:
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = sr + dr, sc + dc
                    if 0 <= nr < 10 and 0 <= nc < 10:
                        # Если клетка пустая (0) или скрытая (0), ставим маркер
                        # Не перезаписываем попадания
                        if board[nr][nc] == 0:
                            board[nr][nc] = mark