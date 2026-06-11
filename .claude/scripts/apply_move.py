"""
apply_move.py — Applies a validated move to the game state.

Called by subagents after choosing a move. This script:
1. Validates the move first
2. Updates the board
3. Handles special moves (castling, en passant, promotion)
4. Updates castling rights, en passant target, clocks
5. Detects check/checkmate/stalemate for next player
6. Flips the turn
7. Saves updated state

Supports async broadcast callbacks for WebSocket streaming.

Usage:
    python .claude/scripts/apply_move.py <move>
    e.g. python .claude/scripts/apply_move.py e2e4

Output:
    JSON with result status and updated game info
"""

import sys
import json
from typing import Callable, Any
from pathlib import Path

# Add parent directory to path for relative imports
sys.path.insert(0, str(Path(__file__).parent))

from board import (
    load_game_state, save_game_state,
    algebraic_to_index, index_to_algebraic, render_board
)
from validate_move import (
    validate_move, simulate_move, in_check, is_white, is_black
)
from get_legal_moves import generate_all_legal_moves


def apply_move(move_str: str) -> dict[str, Any]:
    """
    Apply a move to the current game state.

    Args:
        move_str: Algebraic notation move string (e.g., 'e2e4', 'e1g1').

    Returns:
        Dictionary with status, move details, and game state info.
    """
    # Step 1: Validate
    valid, reason = validate_move(move_str)
    if not valid:
        return {"status": "invalid", "reason": reason}

    state = load_game_state()
    board = state["board"]
    color = state["turn"]
    castling = state["castling"]

    from_sq = move_str[:2]
    to_sq   = move_str[2:4]
    promotion = move_str[4].upper() if len(move_str) == 5 else None

    fr, fc = algebraic_to_index(from_sq)
    tr, tc = algebraic_to_index(to_sq)
    piece = board[fr][fc]

    captured = board[tr][tc] if board[tr][tc] != "." else None
    new_en_passant = None

    # Step 2: Apply to board
    board[tr][tc] = piece
    board[fr][fc] = "."

    # Step 3: Special moves

    # Castling
    if piece.upper() == "K" and abs(tc - fc) == 2:
        row = fr
        if tc > fc:  # kingside
            board[row][5] = board[row][7]
            board[row][7] = "."
        else:          # queenside
            board[row][3] = board[row][0]
            board[row][0] = "."

    # En passant capture
    ep = state.get("en_passant")
    if piece.upper() == "P" and ep and to_sq == ep:
        ep_capture_row = tr + (1 if color == "white" else -1)
        board[ep_capture_row][tc] = "."
        captured = "p" if color == "white" else "P"

    # Pawn double advance → set en passant target
    if piece.upper() == "P" and abs(tr - fr) == 2:
        ep_row = (fr + tr) // 2
        new_en_passant = index_to_algebraic(ep_row, fc)

    # Promotion
    if piece.upper() == "P":
        back_rank = 0 if color == "white" else 7
        if tr == back_rank:
            promo_piece = promotion or "Q"
            board[tr][tc] = promo_piece if color == "white" else promo_piece.lower()

    # Step 4: Update castling rights
    if piece == "K":
        castling["white_kingside"] = False
        castling["white_queenside"] = False
    if piece == "k":
        castling["black_kingside"] = False
        castling["black_queenside"] = False
    if piece == "R":
        if from_sq == "h1": castling["white_kingside"] = False
        if from_sq == "a1": castling["white_queenside"] = False
    if piece == "r":
        if from_sq == "h8": castling["black_kingside"] = False
        if from_sq == "a8": castling["black_queenside"] = False

    # Step 5: Flip turn
    next_color = "black" if color == "white" else "white"

    # Step 6: Detect check / checkmate / stalemate for next player
    next_in_check = in_check(board, next_color)
    next_legal_moves = generate_all_legal_moves_from_board(board, next_color, state)

    if not next_legal_moves and next_in_check:
        game_status = "checkmate"
    elif not next_legal_moves:
        game_status = "stalemate"
    elif next_in_check:
        game_status = "check"
    else:
        game_status = "active"

    # Step 7: Update halfmove clock (reset on pawn move or capture)
    halfmove = 0 if (piece.upper() == "P" or captured) else state["halfmove_clock"] + 1
    fullmove = state["fullmove_number"] + (1 if color == "black" else 0)

    # Step 8: Record move in history
    move_record = {
        "move": move_str,
        "color": color,
        "piece": piece,
        "from": from_sq,
        "to": to_sq,
        "captured": captured,
        "check": next_in_check,
        "fullmove": fullmove
    }
    state["move_history"].append(move_record)

    # Step 9: Save state
    state.update({
        "board": board,
        "turn": next_color,
        "castling": castling,
        "en_passant": new_en_passant,
        "halfmove_clock": halfmove,
        "fullmove_number": fullmove,
        "status": game_status,
        "in_check": next_color if next_in_check else None
    })
    save_game_state(state)

    return {
        "status": "ok",
        "move_applied": move_str,
        "piece": piece,
        "captured": captured,
        "game_status": game_status,
        "next_turn": next_color,
        "fullmove": fullmove,
        "board_display": render_board(board)
    }


def generate_all_legal_moves_from_board(
    board: list[list[str]],
    color: str,
    state: dict[str, Any]
) -> list[dict[str, Any]]:
    """Lightweight wrapper — temporarily writes board to state for legal move gen."""
    import copy
    temp_state = copy.deepcopy(state)
    temp_state["board"] = board
    temp_state["turn"] = color
    save_game_state(temp_state)
    moves = generate_all_legal_moves(color)
    return moves


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python .claude/scripts/apply_move.py <move>")
        sys.exit(1)

    result = apply_move(sys.argv[1])
    print(json.dumps(result, indent=2))

    if result["status"] == "ok":
        print("\n" + result.get("board_display", ""))
        print(f"\nNext turn: {result['next_turn'].capitalize()}")
        print(f"Game status: {result['game_status']}")