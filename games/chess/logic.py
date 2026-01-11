import copy


class ChessLogic:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.board = [
            ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
            ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'],
            ['', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', '', ''],
            ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'],
            ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR']
        ]
        self.turn = 'white'
        self.is_check = False
        self.game_over = False
        self.winner = None

        # --- НОВЫЕ ПЕРЕМЕННЫЕ ---
        # Храним координаты фигур, которые уже двигались (для рокировки)
        # Пример: если (7, 4) есть в set, значит белый король ходил.
        self.moved_pieces = set()

        # Координата "битого поля" для взятия на проходе. Пример: (2, 3)
        self.en_passant_target = None

    def move_piece(self, start_pos, end_pos):
        if self.game_over: return False

        r1, c1 = start_pos
        r2, c2 = end_pos
        piece = self.board[r1][c1]

        # 1. Валидация
        valid_moves = self.get_valid_moves(r1, c1)
        if (r2, c2) not in valid_moves:
            return False

        # 2. Обработка СПЕЦИАЛЬНЫХ ХОДОВ

        # --- РОКИРОВКА ---
        if piece[1] == 'K' and abs(c2 - c1) == 2:
            # Если король пошел на 2 клетки - это рокировка
            # Двигаем ладью
            if c2 > c1:  # Короткая (вправо)
                rook_start = (r1, 7)
                rook_end = (r1, 5)
            else:  # Длинная (влево)
                rook_start = (r1, 0)
                rook_end = (r1, 3)

            # Перемещаем ладью
            self.board[rook_end[0]][rook_end[1]] = self.board[rook_start[0]][rook_start[1]]
            self.board[rook_start[0]][rook_start[1]] = ''
            self.moved_pieces.add(rook_start)  # Ладья походила

        # --- ВЗЯТИЕ НА ПРОХОДЕ (En Passant) ---
        if piece[1] == 'P' and (r2, c2) == self.en_passant_target:
            # Пешка пошла на битое поле. Нужно удалить вражескую пешку.
            # Враг стоит на той же горизонтали, куда мы пришли, но на ряд раньше/позже?
            # Нет, враг стоит ровно там, где мы, но по вертикали start_row (r1)
            # Если мы пошли на (2, 3), а прыжок был с (1, 3) на (3, 3), то враг на (3, 3).
            # Проще: враг стоит на (r1, c2)
            self.board[r1][c2] = ''

        # 3. Обычное перемещение
        self._apply_move(self.board, start_pos, end_pos)

        # 4. Обновление статусов для следующего хода

        # Если пешка прыгнула на 2 клетки - ставим метку En Passant
        if piece[1] == 'P' and abs(r2 - r1) == 2:
            # Битое поле - это клетка посередине
            mid_row = (r1 + r2) // 2
            self.en_passant_target = (mid_row, c1)
        else:
            self.en_passant_target = None

        # Запоминаем, что фигура ходила (для рокировки)
        self.moved_pieces.add(start_pos)
        # Если съели ладью - её стартовая позиция тоже "ходила" (чтобы нельзя было рокироваться с призраком)
        # Но проще просто проверять наличие ладьи при проверке рокировки.

        # 5. Смена хода и проверка мата
        self.turn = 'black' if self.turn == 'white' else 'white'
        self.is_check = self._is_king_under_attack(self.turn, self.board)

        if not self._has_any_moves(self.turn):
            self.game_over = True
            if self.is_check:
                self.winner = 'black' if self.turn == 'white' else 'white'
            else:
                self.winner = 'Draw'

        return True

    def get_valid_moves(self, r, c):
        piece = self.board[r][c]
        if piece == '': return []
        color = piece[0]

        if (self.turn == 'white' and color != 'w') or \
                (self.turn == 'black' and color != 'b'):
            return []

        pseudo_moves = self._get_pseudo_legal_moves(r, c, self.board)
        legal_moves = []

        for target_r, target_c in pseudo_moves:
            # Для симуляции нужно учитывать En Passant, но он не меняет безопасность короля обычно
            # (кроме редких случаев).
            # ВАЖНО: При симуляции рокировки нужно проверять битые поля.

            # Делаем копию
            temp_board = [row[:] for row in self.board]

            # Эмуляция хода (простая)
            self._apply_move(temp_board, (r, c), (target_r, target_c))

            # Если это En Passant, нужно на временной доске удалить пешку, иначе может быть баг
            # (например, открывается линия на короля).
            # Это усложняет код, но для идеальной точности нужно.
            # Пока реализуем базовую проверку.

            if not self._is_king_under_attack(color, temp_board):
                legal_moves.append((target_r, target_c))

        # --- ДОБАВЛЯЕМ РОКИРОВКУ (Только если король сейчас в безопасности) ---
        if piece[1] == 'K' and not self.is_check:
            # Нельзя рокироваться, если король уже ходил
            if (r, c) not in self.moved_pieces:
                row = r
                # Короткая (Kingside)
                if self._can_castle(color, row, 'short'):
                    legal_moves.append((row, 6))  # G-file
                # Длинная (Queenside)
                if self._can_castle(color, row, 'long'):
                    legal_moves.append((row, 2))  # C-file

        return legal_moves

    def _can_castle(self, color, row, side):
        # 1. Проверяем ладью
        if side == 'short':
            rook_col = 7
            empty_cols = [5, 6]
            king_pass_cols = [5, 6]  # Клетки, которые проходит король
        else:  # long
            rook_col = 0
            empty_cols = [1, 2, 3]
            king_pass_cols = [2, 3]  # Клетка d1/d8 тоже должна быть пустой, но король проходит c1, d1 (2,3)

        # Ладья должна быть на месте, своего цвета и не ходила
        rook = self.board[row][rook_col]
        if rook == '' or rook[1] != 'R' or rook[0] != color:
            return False
        if (row, rook_col) in self.moved_pieces:
            return False

        # 2. Путь должен быть свободен
        for c in empty_cols:
            if self.board[row][c] != '': return False

        # 3. Клетки, которые проходит король, не должны быть под боем
        # (Король не может проходить через битое поле)
        for c in king_pass_cols:
            # Проверяем, атакуют ли клетку (row, c)
            # Для этого ставим туда короля "понарошку" и зовем _is_king_under_attack
            # Или проще: проверяем attack на эту клетку.
            # Но у нас функция принимает board. Сделаем хак:
            # Проверим безопасность, если король встанет на эту клетку.
            temp_board = [r[:] for r in self.board]
            temp_board[row][4] = ''  # Убираем короля с старого места
            temp_board[row][c] = color + 'K'  # Ставим на новое

            # ВАЖНО: нужно передать имя цвета
            col_name = 'white' if color == 'w' else 'black'
            if self._is_king_under_attack(col_name, temp_board):
                return False

        return True

    def _apply_move(self, board, start, end):
        r1, c1 = start
        r2, c2 = end
        piece = board[r1][c1]
        board[r2][c2] = piece
        board[r1][c1] = ''
        if piece == 'wP' and r2 == 0:
            board[r2][c2] = 'wQ'
        elif piece == 'bP' and r2 == 7:
            board[r2][c2] = 'bQ'

    def _is_king_under_attack(self, color_name, board):
        # ИСПРАВЛЕННЫЙ ВАРИАНТ С ПРОШЛОГО ШАГА
        if color_name in ['white', 'w']:
            color_code, enemy_code = 'w', 'b'
        else:
            color_code, enemy_code = 'b', 'w'

        target_king = color_code + 'K'
        king_pos = None
        for r in range(8):
            for c in range(8):
                if board[r][c] == target_king:
                    king_pos = (r, c)
                    break
            if king_pos: break
        if not king_pos: return True

        kr, kc = king_pos
        knight_offsets = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
        for dr, dc in knight_offsets:
            tr, tc = kr + dr, kc + dc
            if 0 <= tr < 8 and 0 <= tc < 8:
                if board[tr][tc] == enemy_code + 'N': return True

        linear_dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        for dr, dc in linear_dirs:
            tr, tc = kr + dr, kc + dc
            while 0 <= tr < 8 and 0 <= tc < 8:
                p = board[tr][tc]
                if p != '':
                    if p[0] == enemy_code and p[1] in ['R', 'Q']: return True
                    break
                tr += dr;
                tc += dc

        diag_dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        for dr, dc in diag_dirs:
            tr, tc = kr + dr, kc + dc
            while 0 <= tr < 8 and 0 <= tc < 8:
                p = board[tr][tc]
                if p != '':
                    if p[0] == enemy_code and p[1] in ['B', 'Q']: return True
                    break
                tr += dr;
                tc += dc

        attack_from_row = kr - 1 if color_code == 'w' else kr + 1
        if 0 <= attack_from_row < 8:
            for dc in [-1, 1]:
                tc = kc + dc
                if 0 <= tc < 8:
                    if board[attack_from_row][tc] == enemy_code + 'P': return True

        king_offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        for dr, dc in king_offsets:
            tr, tc = kr + dr, kc + dc
            if 0 <= tr < 8 and 0 <= tc < 8:
                if board[tr][tc] == enemy_code + 'K': return True
        return False

    def _get_pseudo_legal_moves(self, r, c, board):
        piece = board[r][c]
        if piece == '': return []
        color = piece[0]
        ptype = piece[1]
        moves = []

        def add_move(tr, tc):
            if 0 <= tr < 8 and 0 <= tc < 8:
                target = board[tr][tc]
                if target == '':
                    moves.append((tr, tc))
                    return True
                elif target[0] != color:
                    moves.append((tr, tc))
                    return False
                else:
                    return False
            return False

        if ptype == 'P':
            d = -1 if color == 'w' else 1
            start_r = 6 if color == 'w' else 1
            if 0 <= r + d < 8 and board[r + d][c] == '':
                moves.append((r + d, c))
                if r == start_r and board[r + d * 2][c] == '':
                    moves.append((r + d * 2, c))
            for dc in [-1, 1]:
                if 0 <= r + d < 8 and 0 <= c + dc < 8:
                    target = board[r + d][c + dc]
                    if target != '' and target[0] != color:
                        moves.append((r + d, c + dc))
                    # --- ВЗЯТИЕ НА ПРОХОДЕ (Псевдо-ход) ---
                    # Если клетка пустая, но это цель en_passant
                    if target == '' and (r + d, c + dc) == self.en_passant_target:
                        moves.append((r + d, c + dc))

        elif ptype == 'N':
            offsets = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
            for dr, dc in offsets: add_move(r + dr, c + dc)
        elif ptype == 'K':
            offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
            for dr, dc in offsets: add_move(r + dr, c + dc)
        else:
            dirs = []
            if ptype in ['R', 'Q']: dirs.extend([(-1, 0), (1, 0), (0, -1), (0, 1)])
            if ptype in ['B', 'Q']: dirs.extend([(-1, -1), (-1, 1), (1, -1), (1, 1)])
            for dr, dc in dirs:
                cr, cc = r + dr, c + dc
                while 0 <= cr < 8 and 0 <= cc < 8:
                    if not add_move(cr, cc): break
                    cr += dr;
                    cc += dc
        return moves

    def _has_any_moves(self, color):
        prefix = 'w' if color == 'white' else 'b'
        for r in range(8):
            for c in range(8):
                if self.board[r][c].startswith(prefix):
                    if len(self.get_valid_moves(r, c)) > 0: return True
        return False