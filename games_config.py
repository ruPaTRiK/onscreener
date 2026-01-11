# Импортируем классы игр, чтобы передать их в конфиг
from games.checkers.ui import CheckersGame
from games.tic_tac_toe.ui import TicTacToeGame
from games.chess.ui import ChessGame
from games.battleship.ui import BattleshipGame

GAMES_CONFIG = [
    {
        "id": "checkers",
        "title": "Шашки",
        "class": CheckersGame,
        "image": "assets/checkers.jpg",
        "tags": ["all", "2_players", "online"],
        "color": "#D18B47"
    },
    {
        "id": "chess",
        "title": "Шахматы",
        "class": ChessGame,
        "image": "assets/chess.jpg",
        "tags": ["all", "2_players", "online"],
        "color": "#8D6E63" # Коричневый
    },
    {
        "id": "tic_tac_toe",
        "title": "Крестики-Нолики",
        "class": TicTacToeGame,
        "image": "assets/ttt.jpg",
        "tags": ["all", "2_players", "online"],
        "color": "#607D8B"  # Серо-синий цвет
    },
    {
        "id": "battleship",
        "title": "Морской бой",
        "class": BattleshipGame,
        "image": "assets/battleship.jpg",
        "tags": ["all", "2_players", "online"],
        "color": "#1565C0"
    },
]