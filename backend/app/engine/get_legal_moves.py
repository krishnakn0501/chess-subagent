"""
get_legal_moves.py — Returns all legal moves for a given color.

Used by both subagents to know what moves are available before choosing.

Usage:
    python backend/app/engine/get_legal_moves.py white
    python backend/app/engine/get_legal_moves.py black

Output: JSON list of move objects with from_sq, to_sq, move_str, piece, capture
"""

import sys
import json
from typing import Any
from pathlib import Path

# Add parent directory to path for relative imports
sys.path.insert(0, str(Path(__file__).parent))

from board import load_game_state, index_to_algebraic, algebraic_to_index
from validate_move import (
    get_piece_moves, is_white, is_black, is_enemy,
    simulate_move, in_check, validate_castling, find_king
)


def generate_all_legal_moves(color: str) -> list[dict[str, Any]]:
    """
    Generate all legal moves for a given player.

    Args:
        color: Either "white" or "black".

    Returns:
        List of move dictionaries with move details.
    """
    state = load_game_state()
    board = state["board"]
    castling = state.get("castling", {})
    en_passant = state.get("en_passant")

    legal_moves: list[dict[str, Any]] = []

    for fr in range(8):
        for fc in range(8):
            piece = board[fr][fc]
            if piece == ".":
                continue
            if color == "white" and not is_white(piece):
                continue
            if color == "black" and not is_black(piece):
                continue

            from_sq = index_to_algebraic(fr, fc)
            targets = get_piece_moves(board, fr, fc, color, en_passant)

            for tr, tc in targets:
                to_sq = index_to_algebraic(tr, tc)
                new_board = simulate_move(board, fr, fc, tr, tc)

                # Skip moves that leave own king in check
                if in_check(new_board, color):
                    continue

                capture = board[tr][tc] if board[tr][tc] != "." else None
                move_str = f"{from_sq}{to_sq}"

                # Handle pawn promotion
                back_rank = 0 if color == "white" else 7
                if piece.upper() == "P" and tr == back_rank:
                    for promo in ["Q", "R", "B", "N"]:
                        legal_moves.append({
                            "move_str": move_str + promo,
                            "from_sq": from_sq,
                            "to_sq": to_sq,
                            "piece": piece,
                            "capture": capture,
                            "promotion": promo,
                            "special": "promotion"
                        })
                    continue

                legal_moves.append({
                    "move_str": move_str,
                    "from_sq": from_sq,
                    "to_sq": to_sq,
                    "piece": piece,
                    "capture": capture,
                    "promotion": None,
                    "special": None
                })

    # Castling
    row = 7 if color == "white" else 0
    for side in ["kingside", "queenside"]:
        if validate_castling(board, color, side, castling):
            king_col = 4
            to_col = 6 if side == "kingside" else 2
            from_sq = index_to_algebraic(row, king_col)
            to_sq = index_to_algebraic(row, to_col)
            legal_moves.append({
                "move_str": f"{from_sq}{to_sq}",
                "from_sq": from_sq,
                "to_sq": to_sq,
                "piece": "K" if color == "white" else "k",
                "capture": None,
                "promotion": None,
                "special": f"castling_{side}"
            })

    return legal_moves


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("white", "black"):
        print("Usage: python backend/app/engine/get_legal_moves.py <white|black>")
        sys.exit(1)

    color = sys.argv[1]
    moves = generate_all_legal_moves(color)

    if not moves:
        print(json.dumps({"status": "no_legal_moves", "color": color, "moves": []}))
    else:
        print(json.dumps({
            "status": "ok",
            "color": color,
            "count": len(moves),
            "moves": moves
        }, indent=2))
