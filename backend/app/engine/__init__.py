"""
Engine module for Chess Arena backend.

Contains board representation, move validation, and move application logic.
All file paths are resolved from the project root directory.
"""

from .board import (
    load_game_state,
    save_game_state,
    init_game_state,
    render_board,
    fen_to_board,
    board_to_fen_position,
    algebraic_to_index,
    index_to_algebraic
)
from .validate_move import validate_move
from .apply_move import apply_move, apply_move_with_broadcast
from .get_legal_moves import generate_all_legal_moves

__all__ = [
    "load_game_state",
    "save_game_state",
    "init_game_state",
    "render_board",
    "fen_to_board",
    "board_to_fen_position",
    "algebraic_to_index",
    "index_to_algebraic",
    "validate_move",
    "apply_move",
    "apply_move_with_broadcast",
    "generate_all_legal_moves"
]
