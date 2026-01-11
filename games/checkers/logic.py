class CheckersLogic:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.board = self._create_board()
        self.turn = 'white'
        self.lock_piece = None  # Если шашка рубит серию, она "залочена"
        self.game_over = False
        self.winner = None  # 'white', 'black' или 'Draw'

    def _create_board(self):
        board = [[0] * 8 for _ in range(8)]
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 == 1:
                    if row < 3:
                        board[row][col] = 2  # Черные
                    elif row > 4:
                        board[row][col] = 1  # Белые
        return board

    def move_piece(self, start_pos, end_pos):
        if self.game_over: return False

        r1, c1 = start_pos
        r2, c2 = end_pos

        # Если есть активная серия взятий (lock_piece), ходим только ей
        if self.lock_piece and self.lock_piece != start_pos:
            return False

        piece = self.board[r1][c1]
        if piece == 0: return False
        if self.board[r2][c2] != 0: return False

        # Очередность
        is_piece_white = (piece in [1, 3])
        is_white_turn = (self.turn == 'white')
        if is_piece_white != is_white_turn: return False

        d_row = r2 - r1
        d_col = c2 - c1
        if abs(d_row) != abs(d_col): return False

        captured = False

        # --- ПРОВЕРКА ОБЯЗАТЕЛЬНОГО ВЗЯТИЯ ---
        is_capture_move = False

        if piece in [1, 2] and abs(d_row) == 2:
            is_capture_move = True
        elif piece in [3, 4]:
            step_r = 1 if d_row > 0 else -1
            step_c = 1 if d_col > 0 else -1
            cur_r, cur_c = r1 + step_r, c1 + step_c
            while (cur_r, cur_c) != (r2, c2):
                if self.board[cur_r][cur_c] != 0:
                    is_capture_move = True
                    break
                cur_r += step_r
                cur_c += step_c

        # Если это НЕ взятие, но на доске ЕСТЬ кого бить -> запрещаем ход
        if not is_capture_move and not self.lock_piece:
            if self._has_valid_captures(self.turn):
                return False

        # === ЛОГИКА ПРОСТЫХ (1, 2) ===
        if piece in [1, 2]:
            if abs(d_row) == 1:
                if piece == 1 and d_row == -1: return self._finalize_move(start_pos, end_pos, captured=False)
                if piece == 2 and d_row == 1:  return self._finalize_move(start_pos, end_pos, captured=False)

            elif abs(d_row) == 2:
                mid_r, mid_c = (r1 + r2) // 2, (c1 + c2) // 2
                victim = self.board[mid_r][mid_c]
                if victim == 0: return False

                victim_is_white = (victim in [1, 3])
                if is_piece_white == victim_is_white: return False

                self.board[mid_r][mid_c] = 0
                return self._finalize_move(start_pos, end_pos, captured=True)

        # === ЛОГИКА ДАМОК (3, 4) ===
        elif piece in [3, 4]:
            step_r = 1 if d_row > 0 else -1
            step_c = 1 if d_col > 0 else -1

            obstacles = []
            cur_r, cur_c = r1 + step_r, c1 + step_c
            while (cur_r, cur_c) != (r2, c2):
                if self.board[cur_r][cur_c] != 0:
                    obstacles.append((cur_r, cur_c))
                cur_r += step_r
                cur_c += step_c

            if len(obstacles) == 0:
                if self.lock_piece: return False
                return self._finalize_move(start_pos, end_pos, captured=False)

            elif len(obstacles) == 1:
                v_r, v_c = obstacles[0]
                victim = self.board[v_r][v_c]
                victim_is_white = (victim in [1, 3])
                if is_piece_white == victim_is_white: return False

                self.board[v_r][v_c] = 0
                return self._finalize_move(start_pos, end_pos, captured=True)

            else:
                return False

        return False

    def _finalize_move(self, start_pos, end_pos, captured):
        r1, c1 = start_pos
        r2, c2 = end_pos
        piece = self.board[r1][c1]

        self.board[r2][c2] = piece
        self.board[r1][c1] = 0

        # Превращение в дамку
        if piece == 1 and r2 == 0:
            self.board[r2][c2] = 3
        elif piece == 2 and r2 == 7:
            self.board[r2][c2] = 4

        # Логика серии взятий
        if captured:
            if self._can_capture_from(r2, c2):
                self.lock_piece = (r2, c2)
                return True  # Ход не меняется, игра не заканчивается

        self.lock_piece = None

        # Смена хода
        self.turn = 'black' if self.turn == 'white' else 'white'

        # --- ПРОВЕРКА ПОБЕДЫ ---
        # Проверяем, есть ли ходы у НОВОГО игрока
        if not self._has_any_moves(self.turn):
            self.game_over = True
            # Если новый игрок (чей сейчас ход) не может ходить, значит победил предыдущий
            self.winner = 'black' if self.turn == 'white' else 'white'

        return True

    def _has_any_moves(self, color):
        """Проверяет, есть ли у игрока color легальные ходы"""
        # Сначала проверяем обязательные взятия (быстрая проверка)
        if self._has_valid_captures(color):
            return True

        # Если взятий нет, проверяем обычные ходы
        target_pieces = [1, 3] if color == 'white' else [2, 4]

        for r in range(8):
            for c in range(8):
                if self.board[r][c] in target_pieces:
                    # Если хотя бы одна шашка может куда-то пойти
                    if len(self.get_valid_moves(r, c)) > 0:
                        return True
        return False

    def _has_valid_captures(self, turn_color):
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece == 0: continue

                is_piece_white = (piece in [1, 3])
                is_turn_white = (turn_color == 'white')

                if is_piece_white == is_turn_white:
                    if self._can_capture_from(r, c):
                        return True
        return False

    def _can_capture_from(self, r, c):
        piece = self.board[r][c]
        if piece == 0: return False

        is_piece_white = (piece in [1, 3])
        directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]

        if piece in [1, 2]:
            for dr, dc in directions:
                target_r, target_c = r + 2 * dr, c + 2 * dc
                mid_r, mid_c = r + dr, c + dc

                if 0 <= target_r < 8 and 0 <= target_c < 8:
                    if self.board[target_r][target_c] == 0:
                        victim = self.board[mid_r][mid_c]
                        if victim != 0:
                            victim_is_white = (victim in [1, 3])
                            if is_piece_white != victim_is_white:
                                return True

        elif piece in [3, 4]:
            for dr, dc in directions:
                cur_r, cur_c = r + dr, c + dc
                found_enemy = False

                while 0 <= cur_r < 8 and 0 <= cur_c < 8:
                    cell = self.board[cur_r][cur_c]
                    if cell == 0:
                        if found_enemy: return True
                    else:
                        if found_enemy: break
                        cell_is_white = (cell in [1, 3])
                        if is_piece_white == cell_is_white:
                            break
                        else:
                            found_enemy = True

                    cur_r += dr
                    cur_c += dc

        return False

    def get_valid_moves(self, row, col):
        """Возвращает список координат (r, c), куда может походить фигура"""
        moves = []
        piece = self.board[row][col]
        if piece == 0: return []

        # 1. Проверяем чей ход и блокировки
        if self.turn == 'white' and piece not in [1, 3]: return []
        if self.turn == 'black' and piece not in [2, 4]: return []
        if self.lock_piece and self.lock_piece != (row, col): return []

        # 2. Определяем режим: обязаны бить или нет
        must_capture = self._has_valid_captures(self.turn) or (self.lock_piece is not None)

        # 3. Перебираем направления
        directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]

        if piece in [1, 2]:  # Простые
            for dr, dc in directions:
                # Проверяем тихий ход (только если не обязаны бить)
                if not must_capture:
                    t_r, t_c = row + dr, col + dc
                    if 0 <= t_r < 8 and 0 <= t_c < 8 and self.board[t_r][t_c] == 0:
                        # Учитываем направление пешек
                        if (piece == 1 and dr == -1) or (piece == 2 and dr == 1):
                            moves.append((t_r, t_c))

                # Проверяем бой
                j_r, j_c = row + 2 * dr, col + 2 * dc
                m_r, m_c = row + dr, col + dc
                if 0 <= j_r < 8 and 0 <= j_c < 8 and self.board[j_r][j_c] == 0:
                    victim = self.board[m_r][m_c]
                    if victim != 0:
                        is_me_white = (piece in [1, 3])
                        is_vic_white = (victim in [1, 3])
                        if is_me_white != is_vic_white:
                            moves.append((j_r, j_c))

        elif piece in [3, 4]:  # Дамки
            for dr, dc in directions:
                cur_r, cur_c = row + dr, col + dc
                found_enemy = False

                while 0 <= cur_r < 8 and 0 <= cur_c < 8:
                    cell = self.board[cur_r][cur_c]

                    if cell == 0:
                        # Если нашли врага - это бой. Если не нашли - тихий ход.
                        if found_enemy:
                            moves.append((cur_r, cur_c))
                        elif not must_capture:
                            moves.append((cur_r, cur_c))
                    else:
                        if found_enemy: break  # Второй враг/препятствие

                        is_me_white = (piece in [1, 3])
                        is_cell_white = (cell in [1, 3])

                        if is_me_white == is_cell_white: break  # Своя фигура

                        # Враг найден
                        found_enemy = True
                        if not must_capture:
                            # Если мы встретили врага, а до этого считали тихие ходы в этом направлении
                            # то после врага тихих ходов быть не может (только бои)
                            pass

                    cur_r += dr
                    cur_c += dc

        return moves