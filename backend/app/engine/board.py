"""
board.py — Core chess board representation.

Handles:
- Board state as an 8x8 grid
- FEN string parsing and export
- Terminal rendering
- Piece lookup helpers
- Game state persistence to project root/game_state/
- Captured pieces tracking

Piece encoding:
  White: K Q R B N P  (uppercase)
  Black: k q r b n p  (lowercase)
  Empty: '.'
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any


# Project root is 3 levels up from this file (backend/app/engine/ -> project_root)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
GAME_STATE_PATH = PROJECT_ROOT / "game_state" / "current.json"
PGN_PATH = PROJECT_ROOT / "game_state" / "last_game.pgn"

# Starting position in FEN
STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Starting piece counts for a full chess game
STARTING_WHITE_PIECES: dict[str, int] = {"K": 1, "Q": 1, "R": 2, "B": 2, "N": 2, "P": 8}
STARTING_BLACK_PIECES: dict[str, int] = {"k": 1, "q": 1, "r": 2, "b": 2, "n": 2, "p": 8}


def get_captured_pieces(fen: str) -> dict[str, list[str]]:
    """
    Calculate captured pieces using the Dynamic Count Approach.

    Parses the FEN string to count remaining pieces on the board,
    subtracts from starting counts, and returns the missing pieces
    (i.e., captured pieces).

    Args:
        fen: Current FEN string (只需 the position part is parsed)

    Returns:
        Dictionary with two keys:
        - "captured_by_white": List of captured black pieces (e.g., ["p", "n"])
        - "captured_by_black": List of captured white pieces (e.g., ["P", "R"])
        Both lists are sorted for consistent output.
    """
    # Parse the position component (first part) of FEN
    position = fen.split()[0] if fen else ""

    # Count pieces currently on the board
    current_pieces: dict[str, int] = Counter()
    for rank_str in position.split("/"):
        for ch in rank_str:
            if ch.isalpha():
                current_pieces[ch] += 1

    # Calculate captured pieces by subtracting current from starting
    captured_by_white: list[str] = []  # Black pieces captured by white
    captured_by_black: list[str] = []  # White pieces captured by black

    # Check white pieces (uppercase) - these are captured by black if missing
    for piece_type, starting_count in STARTING_WHITE_PIECES.items():
        current_count = current_pieces.get(piece_type, 0)
        missing = starting_count - current_count
        if missing > 0:
            captured_by_black.extend([piece_type] * missing)

    # Check black pieces (lowercase) - these are captured by white if missing
    for piece_type, starting_count in STARTING_BLACK_PIECES.items():
        current_count = current_pieces.get(piece_type, 0)
        missing = starting_count - current_count
        if missing > 0:
            captured_by_white.extend([piece_type] * missing)

    # Sort for consistent output
    captured_by_white.sort()
    captured_by_black.sort()

    return {
        "captured_by_white": captured_by_white,
        "captured_by_black": captured_by_black
    }


def state_to_fen(state: dict[str, Any]) -> str:
    """
    Convert a game state dictionary to a FEN string.

    Args:
        state: Game state dictionary with board, turn, castling, en_passant, etc.

    Returns:
        FEN string representation of the current position.
    """
    board = state["board"]
    ranks = []

    for rank in board:
        fen_rank = ""
        empty = 0
        for sq in rank:
            if sq == ".":
                empty += 1
            else:
                if empty:
                    fen_rank += str(empty)
                    empty = 0
                fen_rank += sq
        if empty:
            fen_rank += str(empty)
        ranks.append(fen_rank)

    # Build complete FEN
    position = "/".join(ranks)
    turn_char = "w" if state["turn"] == "white" else "b"
    fen = f"{position} {turn_char} "

    # Castling rights
    castling = state.get("castling", {})
    castle_str = ""
    if castling.get("white_kingside"):
        castle_str += "K"
    if castling.get("white_queenside"):
        castle_str += "Q"
    if castling.get("black_kingside"):
        castle_str += "k"
    if castling.get("black_queenside"):
        castle_str += "q"
    fen += castle_str if castle_str else "-"
    fen += " "

    # En passant
    fen += str(state.get("en_passant") or "-")
    fen += f" {state.get('halfmove_clock', 0)} {state.get('fullmove_number', 1)}"

    return fen

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
                if empty:
                    fen_rank += str(empty)
                    empty = 0
                fen_rank += sq
        if empty:
            fen_rank += str(empty)
        ranks.append(fen_rank)
    return "/".join(ranks)


def uci_to_san(uci_move: str, board: list[list[str]], color: str) -> str:
    """
    Convert a UCI move (e.g. 'e2e4') to Standard Algebraic Notation (e.g. 'e4').

    Args:
        uci_move: Move in UCI format (e.g. 'e2e4', 'e7e8Q')
        board: Current 8x8 board state
        color: 'white' or 'black'

    Returns:
        SAN string (e.g. 'e4', 'Nf3', 'O-O', 'exd5', 'e8=Q')
    """
    if len(uci_move) < 4:
        return uci_move

    from_sq = uci_move[:2]
    to_sq = uci_move[2:4]
    promotion = uci_move[4].upper() if len(uci_move) == 5 else None

    fr, fc = algebraic_to_index(from_sq)
    tr, tc = algebraic_to_index(to_sq)
    piece = board[fr][fc]
    captured = board[tr][tc] != "."

    # Handle en passant capture detection
    is_pawn = piece.upper() == "P"
    if is_pawn and fc != tc and board[tr][tc] == ".":
        captured = True  # en passant

    # Castling
    if piece.upper() == "K" and abs(tc - fc) == 2:
        return "O-O" if tc > fc else "O-O-O"

    san = ""

    # Pawn moves
    if is_pawn:
        if captured:
            san = from_sq[0] + "x" + to_sq  # e.g. "exd5"
        else:
            san = to_sq  # e.g. "e4"
        if promotion:
            san += "=" + promotion
        return san

    # Piece moves (N, B, R, Q, K)
    piece_letter = piece.upper()
    san = piece_letter

    # Check for disambiguation (same piece type can reach same square)
    # Find all pieces of same type and color that can move to to_sq
    same_piece_moves = []
    for r in range(8):
        for c in range(8):
            if (r, c) == (fr, fc):
                continue
            if board[r][c].upper() == piece.upper():
                # Check if same color
                is_same_color = (board[r][c].isupper() == piece.isupper())
                if not is_same_color:
                    continue
                # Check if this piece can reach to_sq (simplified check)
                # For basic disambiguation, just note same-type pieces exist
                same_piece_moves.append((r, c))

    # Simple disambiguation: if another same-type piece exists, add file or rank
    if same_piece_moves:
        # Check if any other same piece can reach the target square
        needs_file = False
        needs_rank = False
        for (r2, c2) in same_piece_moves:
            # Simple: if on same file, need rank; if on same rank, need file
            if c2 == fc:
                needs_rank = True
            if r2 == fr:
                needs_file = True

        if needs_file or needs_rank:
            if needs_file and not needs_rank:
                san += from_sq[0]  # file disambiguation
            elif needs_rank:
                san += from_sq[1]  # rank disambiguation
            else:
                san += from_sq  # full disambiguation

    if captured:
        san += "x"
    san += to_sq

    return san


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

    # Auto-save PGN if game is over
    if state.get("status") in ("checkmate", "stalemate", "draw"):
        export_to_pgn(state)


def export_to_pgn(state: dict[str, Any]) -> None:
    """Export game state to PGN format with Pakistan/India player names."""
    move_history = state.get("move_history", [])
    status = state.get("status", "active")

    # Determine result
    if status == "checkmate":
        winner = "Black" if state.get("turn") == "white" else "White"
        result = "1-0" if winner == "White" else "0-1"
    elif status in ("stalemate", "draw"):
        result = "1/2-1/2"
    else:
        result = "*"

    # Build PGN headers with Pakistan/India
    lines = [
        '[Event "Claude Code Chess Arena — Pakistan vs India"]',
        '[White "Pakistan"]',
        '[Black "India"]',
        f'[Result "{result}"]',
        "",
    ]

    # Reconstruct board state incrementally for SAN conversion
    board = fen_to_board(STARTING_FEN)

    # Format moves with player names
    move_text = ""
    for i, move_entry in enumerate(move_history):
        uci_move = move_entry["move"]
        color = move_entry["color"]

        # Convert UCI to SAN
        san = uci_to_san(uci_move, board, color)

        # Apply the move to our tracking board
        if len(uci_move) >= 4:
            fr, fc = algebraic_to_index(uci_move[:2])
            tr, tc = algebraic_to_index(uci_move[2:4])
            piece = board[fr][fc]
            board[tr][tc] = piece
            board[fr][fc] = "."

            # Handle castling rook movement
            if piece.upper() == "K" and abs(tc - fc) == 2:
                if tc > fc:  # kingside
                    board[fr][5] = board[fr][7]
                    board[fr][7] = "."
                else:  # queenside
                    board[fr][3] = board[fr][0]
                    board[fr][0] = "."

            # Handle promotion
            if piece.upper() == "P" and len(uci_move) == 5:
                promo_piece = uci_move[4].upper()
                board[tr][tc] = promo_piece if color == "white" else promo_piece.lower()

        # Format: move_number. move_string player_name
        if i % 2 == 0:  # White's move
            move_num = (i // 2) + 1
            move_text += f"{move_num}. {san} Pakistan  "
        else:  # Black's move
            move_text += f"{san} India  "

    move_text += result

    lines.append(move_text.strip())

    # Write to file
    PGN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PGN_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")


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
        "captured_pieces": {        # Track captured pieces
            "captured_by_white": [],
            "captured_by_black": []
        },
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
