"""
validate_move.py — Chess move legality enforcement.

Validates any proposed move against full chess rules:
- Piece movement patterns
- Check detection (cannot move into or stay in check)
- Special moves: castling, en passant, promotion
- Turn enforcement

Usage:
    python backend/app/engine/validate_move.py <move>
    e.g. python backend/app/engine/validate_move.py e2e4
"""

import sys
from typing import Callable
from pathlib import Path

# Add parent directory to path for relative imports
sys.path.insert(0, str(Path(__file__).parent))

from board import (
    load_game_state, algebraic_to_index, index_to_algebraic,
    board_to_fen_position, fen_to_board
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def is_white(piece: str) -> bool:
    return piece.isupper() and piece != "."


def is_black(piece: str) -> bool:
    return piece.islower() and piece != "."


def is_enemy(piece: str, color: str) -> bool:
    if piece == ".":
        return False
    return is_black(piece) if color == "white" else is_white(piece)


def is_friendly(piece: str, color: str) -> bool:
    if piece == ".":
        return False
    return is_white(piece) if color == "white" else is_black(piece)


def find_king(board: list[list[str]], color: str) -> tuple[int, int] | None:
    target = "K" if color == "white" else "k"
    for r in range(8):
        for c in range(8):
            if board[r][c] == target:
                return r, c
    return None


def in_check(board: list[list[str]], color: str) -> bool:
    """Return True if `color`'s king is currently attacked."""
    king_pos = find_king(board, color)
    if not king_pos:
        return False
    return is_square_attacked(board, king_pos, color)


def is_square_attacked(board: list[list[str]], pos: tuple[int, int], defender_color: str) -> bool:
    """Return True if `pos` is attacked by any enemy piece."""
    attacker_color = "black" if defender_color == "white" else "white"
    r, c = pos

    # Check knight attacks
    for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
        nr, nc = r+dr, c+dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            p = board[nr][nc]
            if (attacker_color == "white" and p == "N") or \
               (attacker_color == "black" and p == "n"):
                return True

    # Check sliding pieces (rook/queen on ranks/files, bishop/queen on diagonals)
    directions_rook = [(0,1),(0,-1),(1,0),(-1,0)]
    directions_bishop = [(1,1),(1,-1),(-1,1),(-1,-1)]

    rook_pieces   = ("R", "Q") if attacker_color == "white" else ("r", "q")
    bishop_pieces = ("B", "Q") if attacker_color == "white" else ("b", "q")

    for dr, dc in directions_rook:
        nr, nc = r+dr, c+dc
        while 0 <= nr < 8 and 0 <= nc < 8:
            p = board[nr][nc]
            if p != ".":
                if p in rook_pieces:
                    return True
                break
            nr += dr; nc += dc

    for dr, dc in directions_bishop:
        nr, nc = r+dr, c+dc
        while 0 <= nr < 8 and 0 <= nc < 8:
            p = board[nr][nc]
            if p != ".":
                if p in bishop_pieces:
                    return True
                break
            nr += dr; nc += dc

    # Check pawn attacks
    pawn_dirs = [(-1,-1),(-1,1)] if attacker_color == "white" else [(1,-1),(1,1)]
    pawn = "P" if attacker_color == "white" else "p"
    for dr, dc in pawn_dirs:
        nr, nc = r+dr, c+dc
        if 0 <= nr < 8 and 0 <= nc < 8:
            if board[nr][nc] == pawn:
                return True

    # Check king proximity
    enemy_king = "K" if attacker_color == "white" else "k"
    for dr in [-1,0,1]:
        for dc in [-1,0,1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = r+dr, c+dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                if board[nr][nc] == enemy_king:
                    return True

    return False


def simulate_move(board: list[list[str]], fr: int, fc: int, tr: int, tc: int) -> list[list[str]]:
    """Return a new board after applying a simple move (no special moves)."""
    new_board = [row[:] for row in board]
    new_board[tr][tc] = new_board[fr][fc]
    new_board[fr][fc] = "."
    return new_board


# ── Movement pattern generators ──────────────────────────────────────────────

def pawn_moves(board: list[list[str]], fr: int, fc: int, color: str, en_passant: str | None = None) -> list[tuple[int, int]]:
    moves: list[tuple[int, int]] = []
    direction = -1 if color == "white" else 1
    start_row = 6 if color == "white" else 1

    # Forward one
    tr = fr + direction
    if 0 <= tr < 8 and board[tr][fc] == ".":
        moves.append((tr, fc))
        # Forward two from start
        if fr == start_row and board[fr + 2*direction][fc] == ".":
            moves.append((fr + 2*direction, fc))

    # Captures
    for dc in [-1, 1]:
        tc = fc + dc
        if 0 <= tc < 8 and 0 <= tr < 8:
            target = board[tr][tc]
            if is_enemy(target, color):
                moves.append((tr, tc))
            # En passant
            if en_passant and index_to_algebraic(tr, tc) == en_passant:
                moves.append((tr, tc))
    return moves


def knight_moves(board: list[list[str]], fr: int, fc: int, color: str) -> list[tuple[int, int]]:
    moves: list[tuple[int, int]] = []
    for dr, dc in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
        tr, tc = fr+dr, fc+dc
        if 0 <= tr < 8 and 0 <= tc < 8 and not is_friendly(board[tr][tc], color):
            moves.append((tr, tc))
    return moves


def sliding_moves(board: list[list[str]], fr: int, fc: int, color: str, directions: list[tuple[int, int]]) -> list[tuple[int, int]]:
    moves: list[tuple[int, int]] = []
    for dr, dc in directions:
        tr, tc = fr+dr, fc+dc
        while 0 <= tr < 8 and 0 <= tc < 8:
            target = board[tr][tc]
            if target == ".":
                moves.append((tr, tc))
            elif is_enemy(target, color):
                moves.append((tr, tc))
                break
            else:
                break
            tr += dr; tc += dc
    return moves


def king_moves(board: list[list[str]], fr: int, fc: int, color: str) -> list[tuple[int, int]]:
    moves: list[tuple[int, int]] = []
    for dr in [-1,0,1]:
        for dc in [-1,0,1]:
            if dr == 0 and dc == 0:
                continue
            tr, tc = fr+dr, fc+dc
            if 0 <= tr < 8 and 0 <= tc < 8 and not is_friendly(board[tr][tc], color):
                moves.append((tr, tc))
    return moves


def get_piece_moves(board: list[list[str]], fr: int, fc: int, color: str, en_passant: str | None = None) -> list[tuple[int, int]]:
    piece = board[fr][fc].upper()
    if piece == "P": return pawn_moves(board, fr, fc, color, en_passant)
    if piece == "N": return knight_moves(board, fr, fc, color)
    if piece == "R": return sliding_moves(board, fr, fc, color, [(0,1),(0,-1),(1,0),(-1,0)])
    if piece == "B": return sliding_moves(board, fr, fc, color, [(1,1),(1,-1),(-1,1),(-1,-1)])
    if piece == "Q": return sliding_moves(board, fr, fc, color, [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)])
    if piece == "K": return king_moves(board, fr, fc, color)
    return []


# ── Castling ─────────────────────────────────────────────────────────────────

def validate_castling(board: list[list[str]], color: str, side: str, castling_rights: dict) -> bool:
    """Returns True if castling is legal in the current position."""
    key = f"{color}_{side}"
    if not castling_rights.get(key):
        return False

    row = 7 if color == "white" else 0
    king_col = 4

    # Squares between king and rook must be empty
    empty_cols = [5, 6] if side == "kingside" else [1, 2, 3]
    for c in empty_cols:
        if board[row][c] != ".":
            return False

    # King cannot be in check, pass through check, or land in check
    check_cols = [4, 5, 6] if side == "kingside" else [4, 3, 2]
    for c in check_cols:
        test_board = simulate_move(board, row, king_col, row, c)
        if is_square_attacked(test_board, (row, c), color):
            return False

    return True


# ── Main validation ───────────────────────────────────────────────────────────

def validate_move(move_str: str) -> tuple[bool, str]:
    """
    Validate a move string (e.g. 'e2e4', 'e1g1').
    Returns (is_valid, reason_if_invalid).
    """
    state = load_game_state()
    board = state["board"]
    color = state["turn"]
    castling = state.get("castling", {})
    en_passant = state.get("en_passant")

    if len(move_str) < 4:
        return False, f"Move '{move_str}' is too short. Use algebraic form like 'e2e4'."

    from_sq = move_str[:2]
    to_sq   = move_str[2:4]
    promotion = move_str[4].upper() if len(move_str) == 5 else None

    try:
        fr, fc = algebraic_to_index(from_sq)
        tr, tc = algebraic_to_index(to_sq)
    except Exception:
        return False, f"Invalid square in move '{move_str}'."

    piece = board[fr][fc]

    if piece == ".":
        return False, f"No piece on {from_sq}."

    if color == "white" and not is_white(piece):
        return False, f"It is White's turn but {from_sq} has a Black piece ('{piece}')."
    if color == "black" and not is_black(piece):
        return False, f"It is Black's turn but {from_sq} has a White piece ('{piece}')."

    # Castling detection (King moves 2 squares)
    if piece.upper() == "K" and abs(tc - fc) == 2:
        side = "kingside" if tc > fc else "queenside"
        if validate_castling(board, color, side, castling):
            return True, ""
        return False, f"Castling {side} is not legal in this position."

    # Normal moves — check piece can reach target
    legal_targets = get_piece_moves(board, fr, fc, color, en_passant)
    if (tr, tc) not in legal_targets:
        return False, f"'{piece}' on {from_sq} cannot move to {to_sq} by movement rules."

    # Simulate and check for self-check
    new_board = simulate_move(board, fr, fc, tr, tc)
    if in_check(new_board, color):
        return False, f"Move {move_str} leaves your King in check."

    # Promotion validation
    if piece.upper() == "P":
        back_rank = 0 if color == "white" else 7
        if tr == back_rank and not promotion:
            return False, "Pawn reaching back rank must include promotion piece (e.g. e7e8Q)."

    return True, ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backend/app/engine/validate_move.py <move>")
        sys.exit(1)

    move = sys.argv[1]
    valid, reason = validate_move(move)
    if valid:
        print(f"VALID: {move}")
        sys.exit(0)
    else:
        print(f"INVALID: {reason}")
        sys.exit(1)
