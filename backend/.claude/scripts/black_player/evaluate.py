"""
scripts/black-player/evaluate.py
Scores each legal move from Black's perspective.

Black plays dynamically: counterattack, imbalance, complications.
Rewards queenside aggression, open files toward White King,
and tactical shots over quiet positional moves.

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

# Center squares Black wants to control (from Black's view d5/e5 are primary)
CENTER_SQUARES = {(3, 3), (3, 4), (4, 3), (4, 4)}

# Strong outpost squares for Black Knights
KNIGHT_OUTPOSTS_BLACK = {(5, 4), (5, 3), (4, 2), (4, 5)}  # e3,d3,c4,f4

# Black's starting squares
BLACK_START = {
    "n": {(0, 1), (0, 6)},
    "b": {(0, 2), (0, 5)},
    "r": {(0, 0), (0, 7)},
    "q": {(0, 3)},
}

# Queenside pawn storm files (Black attacks here in Sicilian)
QUEENSIDE_FILES = {0, 1, 2}    # a, b, c files


def piece_value(piece: str) -> int:
    return PIECE_VALUES.get(piece.upper(), 0)


def white_king_position(board: list) -> tuple[int, int] | None:
    return find_king(board, "white")


def score_move(move: dict, board: list, state: dict) -> float:
    score = 0.0
    move_str = move["move_str"]
    from_sq = move["from_sq"]
    to_sq = move["to_sq"]
    piece = move["piece"]
    capture = move.get("capture")
    special = move.get("special")

    fr, fc = algebraic_to_index(from_sq)
    tr, tc = algebraic_to_index(to_sq)

    new_board = simulate_move(board, fr, fc, tr, tc)

    # ── 1. Checkmate ────────────────────────────────────────────────────────
    white_moves_after = generate_all_legal_moves_on_board(new_board, "white", state)
    if in_check(new_board, "white") and not white_moves_after:
        return 100000.0

    # ── 2. Captures (MVV-LVA) ────────────────────────────────────────────────
    if capture:
        captured_value = piece_value(capture)
        attacker_value = piece_value(piece)
        score += captured_value * 10 - attacker_value

    # ── 3. Delivering check ──────────────────────────────────────────────────
    if in_check(new_board, "white"):
        score += 8
        # Extra bonus if check creates a discovered attack
        # (moving a piece that was blocking another)
        score += 3  # Simplified: any check is valuable for Black's dynamic play

    # ── 4. Center control ────────────────────────────────────────────────────
    if (tr, tc) in CENTER_SQUARES:
        score += 6
    piece_attacks = get_piece_moves(new_board, tr, tc, "black")
    center_attacks = sum(1 for sq in piece_attacks if sq in CENTER_SQUARES)
    score += center_attacks * 2

    # ── 5. Development bonus ─────────────────────────────────────────────────
    move_num = state.get("fullmove_number", 1)
    if move_num <= 10:
        start_squares = BLACK_START.get(piece.lower(), set())
        if (fr, fc) in start_squares:
            score += 4

    # ── 6. Castling (Black slightly prefers to delay for counterattack) ──────
    if special == "castling_kingside":
        score += 12
    elif special == "castling_queenside":
        score += 15  # Black sometimes prefers queenside for attacking chances

    # ── 7. Queenside pawn storm (Sicilian plan) ───────────────────────────────
    if piece.lower() == "p" and tc in QUEENSIDE_FILES:
        white_king_pos = white_king_position(board)
        # If White king is on kingside (cols 6–7), queenside attack is correct
        if white_king_pos and white_king_pos[1] >= 5:
            advancement = tr  # row 0 = rank 8, row 7 = rank 1 — lower row = further advanced for Black
            score += (8 - advancement) * 0.8  # Reward advanced queenside pawns

    # ── 8. Knight outposts ───────────────────────────────────────────────────
    if piece.lower() == "n" and (tr, tc) in KNIGHT_OUTPOSTS_BLACK:
        score += 5

    # ── 9. Rook on open/semi-open file ────────────────────────────────────────
    if piece.lower() == "r":
        file_col = tc
        file_pieces = [new_board[r][file_col] for r in range(8)]
        if not any(p in ("P", "p") for p in file_pieces):
            score += 6
        elif not any(p == "p" for p in file_pieces):
            score += 3

    # ── 10. Pawn advancement / promotion ─────────────────────────────────────
    if piece.lower() == "p":
        advancement = tr  # lower row = more advanced for Black
        score += (8 - advancement) * 0.4
        if special == "promotion":
            score += 50

    # ── 11. Counterattack bonus (Black values threats over defense) ──────────
    # If White had a strong attack, a counter-threat scores extra
    white_king_pos = white_king_position(new_board)
    if white_king_pos:
        if is_square_attacked(new_board, white_king_pos, "white"):
            score += 4  # Our move pressures the White King zone

    # ── 12. Hanging piece penalty ────────────────────────────────────────────
    if is_square_attacked(new_board, (tr, tc), "black"):
        score -= piece_value(piece) * 7

    # Safety net
    if in_check(new_board, "black"):
        return -99999.0

    return score


def generate_all_legal_moves_on_board(board, color, state):
    import copy
    from board import save_game_state
    temp = copy.deepcopy(state)
    temp["board"] = board
    temp["turn"] = color
    save_game_state(temp)
    moves = generate_all_legal_moves(color)
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
    moves = generate_all_legal_moves("black")
    ranked = rank_moves(moves, board, state)

    print("Top 5 moves for Black:")
    for score, move in ranked[:5]:
        print(f"  {move['move_str']:6s}  score={score:.1f}  piece={move['piece']}  capture={move.get('capture')}")