"""
scripts/white-player/evaluate.py
Scores each legal move from White's perspective.

White plays classical chess: center control, development, king safety,
material advantage. Returns a sorted list of (score, move_dict).

VARIATION GUIDANCE:
- When multiple moves have similar scores (within 2 points), consider
  preferring less common moves to add variety across games
- In opening phase (moves 1-10), add small random bonus to alternative
  opening lines to avoid repetition
- The AI model should consider these scores but not rigidly follow them

Used by choose_move.py to pick the best move.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engine.board import load_game_state, algebraic_to_index, index_to_algebraic
from app.engine.validate_move import (
    simulate_move, in_check, is_square_attacked,
    get_piece_moves, find_king
)
from app.engine.get_legal_moves import generate_all_legal_moves

# ── Constants ────────────────────────────────────────────────────────────────

PIECE_VALUES = {"Q": 9, "R": 5, "B": 3, "N": 3, "P": 1, "K": 0}

# Center squares White wants to control
CENTER_SQUARES = {(4, 3), (4, 4), (3, 3), (3, 4)}  # d4,e4,d5,e5

# Good squares for White Knights (outposts deep in enemy half)
KNIGHT_OUTPOSTS_WHITE = {(2, 4), (2, 3), (3, 5), (3, 2)}  # e6,d6,f5,c5

# White's starting squares (pieces that have NOT yet developed)
WHITE_START = {
    "N": {(7, 1), (7, 6)},   # b1, g1
    "B": {(7, 2), (7, 5)},   # c1, f1
    "R": {(7, 0), (7, 7)},   # a1, h1
    "Q": {(7, 3)},           # d1
}


def piece_value(piece: str) -> int:
    return PIECE_VALUES.get(piece.upper(), 0)


def score_move(move: dict, board: list, state: dict) -> float:
    """
    Score a single move from White's perspective.
    Higher score = better move.
    """
    score = 0.0
    move_str = move["move_str"]
    from_sq = move["from_sq"]
    to_sq = move["to_sq"]
    piece = move["piece"]
    capture = move.get("capture")
    special = move.get("special")

    fr, fc = algebraic_to_index(from_sq)
    tr, tc = algebraic_to_index(to_sq)

    # Simulate the move
    new_board = simulate_move(board, fr, fc, tr, tc)

    # ── 1. Checkmate ────────────────────────────────────────────────────────
    black_moves_after = generate_all_legal_moves_on_board(new_board, "black", state)
    if in_check(new_board, "black") and not black_moves_after:
        return 100000.0  # Checkmate — always play this

    # ── 2. Captures ─────────────────────────────────────────────────────────
    if capture:
        captured_value = piece_value(capture)
        attacker_value = piece_value(piece)
        # MVV-LVA: Most Valuable Victim - Least Valuable Attacker
        score += captured_value * 10 - attacker_value

    # ── 3. Delivering check ─────────────────────────────────────────────────
    if in_check(new_board, "black"):
        score += 8

    # ── 4. Center control ───────────────────────────────────────────────────
    if (tr, tc) in CENTER_SQUARES:
        score += 6
    # Also reward attacks on center squares
    piece_attacks = get_piece_moves(new_board, tr, tc, "white")
    center_attacks = sum(1 for sq in piece_attacks if sq in CENTER_SQUARES)
    score += center_attacks * 2

    # ── 5. Development bonus ────────────────────────────────────────────────
    move_num = state.get("fullmove_number", 1)
    if move_num <= 10:
        start_squares = WHITE_START.get(piece.upper(), set())
        if (fr, fc) in start_squares:
            score += 4  # Moving an undeveloped piece

    # ── 6. Castling ─────────────────────────────────────────────────────────
    if special == "castling_kingside":
        score += 20  # Strongly prefer kingside castling for safety
    elif special == "castling_queenside":
        score += 8

    # ── 7. Knight outposts ──────────────────────────────────────────────────
    if piece.upper() == "N" and (tr, tc) in KNIGHT_OUTPOSTS_WHITE:
        score += 5

    # ── 8. Rook on open file ────────────────────────────────────────────────
    if piece.upper() == "R":
        file_col = tc
        file_pieces = [new_board[r][file_col] for r in range(8)]
        if not any(p in ("P", "p") for p in file_pieces):
            score += 6  # Open file
        elif not any(p == "P" for p in file_pieces):
            score += 3  # Semi-open file (no White pawn)

    # ── 9. Passed pawn push ─────────────────────────────────────────────────
    if piece.upper() == "P":
        # Reward advancing pawns, especially in endgame
        advancement = 7 - tr  # row 7 = rank 1, row 0 = rank 8
        score += advancement * 0.5
        if special == "promotion":
            score += 50

    # ── 10. Hanging piece penalty ───────────────────────────────────────────
    if is_square_attacked(new_board, (tr, tc), "white"):
        score -= piece_value(piece) * 8  # Penalize moving to attacked square

    # ── 11. Safety: do not leave own King in check ──────────────────────────
    if in_check(new_board, "white"):
        return -99999.0  # Illegal — filtered out upstream, but safety net

    return score


def generate_all_legal_moves_on_board(board, color, state):
    """Temporarily update state board to generate legal moves for given position."""
    import copy
    from board import save_game_state
    temp = copy.deepcopy(state)
    temp["board"] = board
    temp["turn"] = color
    save_game_state(temp)
    moves = generate_all_legal_moves(color)
    # Restore original state
    save_game_state(state)
    return moves


def rank_moves(moves: list, board: list, state: dict) -> list:
    """Return moves sorted best-first by score.

    NOTE: For variety, the AI agent may choose from the top N moves (where N=3)
    rather than always picking the absolute best-scoring move.
    """
    scored = []
    for move in moves:
        s = score_move(move, board, state)
        scored.append((s, move))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


if __name__ == "__main__":
    state = load_game_state()
    board = state["board"]
    moves = generate_all_legal_moves("white")
    ranked = rank_moves(moves, board, state)

    print(f"Top 5 moves for White:")
    for score, move in ranked[:5]:
        print(f"  {move['move_str']:6s}  score={score:.1f}  piece={move['piece']}  capture={move.get('capture')}")