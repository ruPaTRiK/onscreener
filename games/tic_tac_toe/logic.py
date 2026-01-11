class TicTacToeLogic:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        # Пустая строка - пусто, 'X' - крестик, 'O' - нолик
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.turn = 'X'  # X всегда ходит первым
        self.winner = None  # 'X', 'O', 'Draw' или None
        self.game_over = False
        self.winning_line = []  # Координаты победной линии [(0,0), (0,1), (0,2)]

    def make_move(self, row, col):
        if self.game_over:
            return False

        if self.board[row][col] != '':
            return False

        # Записываем ход
        self.board[row][col] = self.turn

        # Проверяем победу
        if self._check_win():
            self.winner = self.turn
            self.game_over = True
        elif self._check_draw():
            self.winner = 'Draw'
            self.game_over = True
        else:
            # Смена хода
            self.turn = 'O' if self.turn == 'X' else 'X'

        return True

    def _check_win(self):
        b = self.board
        # Проверка строк и столбцов
        for i in range(3):
            # Строки
            if b[i][0] == b[i][1] == b[i][2] != '':
                self.winning_line = [(i, 0), (i, 1), (i, 2)]
                return True
            # Столбцы
            if b[0][i] == b[1][i] == b[2][i] != '':
                self.winning_line = [(0, i), (1, i), (2, i)]
                return True

        # Диагонали
        if b[0][0] == b[1][1] == b[2][2] != '':
            self.winning_line = [(0, 0), (1, 1), (2, 2)]
            return True
        if b[0][2] == b[1][1] == b[2][0] != '':
            self.winning_line = [(0, 2), (1, 1), (2, 0)]
            return True

        return False

    def _check_draw(self):
        for row in self.board:
            if '' in row:
                return False
        return True