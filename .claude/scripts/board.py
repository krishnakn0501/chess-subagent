"""
board.py — Core chess board representation.

Handles:
- Board state as an 8x8 grid
- FEN string parsing and export
- Terminal rendering
- Piece lookup helpers
- Game state persistence to project root/game_state/

Piece encoding:
  White: K Q R B N P  (uppercase)
  Black: k q r b n p  (lowercase)
  Empty: '.'
"""

import json
from pathlib import Path
from typing import Any


# Project root is 3 levels up from this file (.claude/scripts/ -> project_root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
GAME_STATE_PATH = PROJECT_ROOT / "game_state" / "current.json"

# Starting position in FEN
STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

PIECE_SYMBOLS: dict[str, str] = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
    ".": "·"
}

PIECE_VALUES: dict[str, int] = {
    "Q": 9, "q": 9,
    "R": 5, "r": 5,
    "B": 3, "b": 3,
    "N": 3, "n": 3,
    "P": 1, "p": 1,
    "K": 0, "k": 0,
}


def fen_to_board(fen: str) -> list[list[str]]:
    """Parse FEN position string into 8x8 grid. Row 0 = rank 8 (Black's back rank)."""
    position = fen.split()[0]
    board: list[list[str]] = []
    for rank_str in position.split("/"):
        rank: list[str] = []
        for ch in rank_str:
            if ch.isdigit():
                rank.extend(["."] * int(ch))
            else:
                rank.append(ch)
        board.append(rank)
    return board


def board_to_fen_position(board: list[list[str]]) -> str:
    """Convert 8x8 grid back to FEN position string."""
    ranks: list[str] = []
    for rank in board:
        fen_rank = ""
        empty = 0
        for sq in rank:
            if sq == ".":
                empty += 1
            else:
                fen_rank += sq
        if empty:
            fen_rank += str(empty)
        ranks.append(fen_rank)
    return "/".join(ranks)


def algebraic_to_index(square: str) -> tuple[int, int]:
    """Convert 'e4' -> (row, col). e.g. a8=(0,0), h1=(7,7)."""
    col = ord(square[0]) - ord("a")
    row = 8 - int(square[1])
    return row, col


def index_to_algebraic(row: int, col: int) -> str:
    """Convert (row, col) -> 'e4'."""
    return chr(ord("a") + col) + str(8 - row)


def load_game_state() -> dict[str, Any]:
    """Load current game state from JSON file at project root."""
    with open(GAME_STATE_PATH) as f:
        return json.load(f)


def save_game_state(state: dict[str, Any]) -> None:
    """Save game state to JSON file at project root."""
    # Ensure directory exists
    GAME_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GAME_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def render_board(board: list[list[str]], use_unicode: bool = True) -> str:
    """Render board as a readable string for terminal output."""
    lines: list[str] = []
    lines.append("  a b c d e f g h")
    lines.append("  +----------------+")
    for i, rank in enumerate(board):
        rank_num = 8 - i
        if use_unicode:
            row = " ".join(PIECE_SYMBOLS.get(p, p) for p in rank)
        else:
            row = " ".join(rank)
        lines.append(f"{rank_num}| {row} |{rank_num}")
    lines.append("  +----------------+")
    lines.append("  a b c d e f g h")
    return "\n".join(lines)


def init_game_state() -> dict[str, Any]:
    """Create and save a fresh game state from the starting position."""
    board = fen_to_board(STARTING_FEN)
    state: dict[str, Any] = {
        "board": board,
        "turn": "white",
        "castling": {
            "white_kingside": True,
            "white_queenside": True,
            "black_kingside": True,
            "black_queenside": True
        },
        "en_passant": None,         # Target square for en passant (e.g. "e6")
        "halfmove_clock": 0,        # For 50-move rule
        "fullmove_number": 1,
        "move_history": [],         # List of moves in algebraic notation
        "status": "active",         # active | check | checkmate | stalemate | draw
        "in_check": None            # "white" | "black" | None
    }
    save_game_state(state)
    return state


if __name__ == "__main__":
    state = init_game_state()
    board = state["board"]
    print(render_board(board))
    print(f"\nTurn: {state['turn'].capitalize()}")
    print(f"Status: {state['status']}")