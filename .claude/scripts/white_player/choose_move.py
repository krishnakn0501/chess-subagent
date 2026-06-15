"""
scripts/white-player/choose_move.py

White subagent's decision-making entry point — AI powered with Long-Term Memory.

The model receives:
  - The current board (visual + FEN-style)
  - All legal moves available
  - Game history so far
  - Its strategic identity (classical, center-control, king safety)
  - Past lessons from similar positions (LTM via mem0)

It responds with a chosen move and reason. No hardcoded book. No static scores.
Every decision is made by Claude reasoning about the actual position.

Features:
- 3-retry logic with exponential backoff for all API calls
- Long-term memory retrieval for similar positions
- Robust error handling

Usage:
  python3 scripts/white-player/choose_move.py
"""

import sys
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "backend" / "app"))

from engine.board import load_game_state, render_board
from engine.get_legal_moves import generate_all_legal_moves
from engine.apply_move import apply_move

API_URL = os.environ.get("ANTHROPIC_BASE_URL") + "/v1/messages"
MODEL   = os.environ.get("ANTHROPIC_MODEL", "sonnet")

MAX_RETRIES = 3
RETRY_DELAY_BASE = 0.5  # seconds


# ── Board context builder ─────────────────────────────────────────────────────

def build_position_context(state: dict, legal_moves: list, ltm_lessons: str = "") -> str:
    """Build a rich text description of the position for the model."""
    board = state["board"]
    history = state.get("move_history", [])
    move_num = state.get("fullmove_number", 1)
    status = state.get("status", "active")
    castling = state.get("castling", {})
    en_passant = state.get("en_passant")

    # Board visual
    board_str = render_board(board, use_unicode=False)

    # Move history (last 10 moves)
    recent = history[-10:] if len(history) > 10 else history
    history_str = ""
    for i, m in enumerate(recent):
        if m["color"] == "white":
            history_str += f"{m['fullmove']}. {m['move']} "
        else:
            history_str += f"{m['move']}  "

    # Material count
    piece_vals = {"Q": 9, "R": 5, "B": 3, "N": 3, "P": 1,
                  "q": 9, "r": 5, "b": 3, "n": 3, "p": 1}
    white_mat = sum(piece_vals.get(p, 0) for row in board for p in row if p.isupper())
    black_mat = sum(piece_vals.get(p, 0) for row in board for p in row if p.islower())
    mat_str = f"White: {white_mat}pts  Black: {black_mat}pts  Delta: {white_mat - black_mat:+d}"

    # Castling rights
    castle_str = []
    if castling.get("white_kingside"):  castle_str.append("O-O available")
    if castling.get("white_queenside"): castle_str.append("O-O-O available")
    if not castle_str: castle_str = ["no castling rights remaining"]

    # Legal moves formatted
    move_list = ", ".join(m["move_str"] for m in legal_moves)

    # Long-term memory section
    ltm_section = ""
    if ltm_lessons and "No relevant" not in ltm_lessons:
        ltm_section = f"""

[LONG-TERM MEMORY: PAST CRITIC FEEDBACK]
{ltm_lessons}

Consider these lessons from similar positions when making your decision."""

    return f"""== CHESS POSITION — MOVE {move_num} ==

BOARD (White=UPPERCASE  Black=lowercase  .=empty):
{board_str}

MATERIAL: {mat_str}
GAME PHASE: {"Opening (moves 1-12)" if move_num <= 12 else "Middlegame (moves 13-30)" if move_num <= 30 else "Endgame"}
STATUS: {status}
EN PASSANT TARGET: {en_passant or "none"}
WHITE CASTLING: {", ".join(castle_str)}
RECENT MOVES: {history_str.strip() or "Game just started"}

LEGAL MOVES FOR WHITE ({len(legal_moves)} total):
{move_list}{ltm_section}"""


# ── System prompt for White ───────────────────────────────────────────────────

WHITE_SYSTEM_PROMPT = """You are the White chess player in a game against a Black AI opponent.

YOUR IDENTITY & STYLE:
- You play classical, principled chess
- Opening preference: King's Pawn (e4), Italian Game (Bc4), early castling
  * But VARY your openings! Sometimes try d4, c4, or Nf3 to keep the opponent guessing
  * If you've played e4 in past games, consider d4 or c4 this time
- Middlegame: control the center, keep pieces active, simplify when ahead in material
- Endgame: activate the King, escort passed pawns, technique over creativity

YOUR DECISION PROCESS — think through these in order:
1. Am I in check? If yes, resolve it first (move King, block, or capture attacker)
2. Can I checkmate or force checkmate in 1-2 moves?
3. Can I win material without losing more in return? (captures, forks, pins, skewers)
4. Can I deliver check that also gains something?
5. Does castling improve my position?
6. What is the best developing or improving move?

VARIETY GUIDANCE:
- If multiple moves score similarly (within 2 points), prefer the less common/expected one
- In opening: consider transpositions and less played lines to surprise opponent
- Avoid repeating the exact same move sequence across games

OUTPUT FORMAT — you must respond with ONLY this token format, nothing else:
[MOVE]
<move_in_algebraic_notation>
[REASON]
<one clear sentence explaining your strategic thinking>

RULES:
- [MOVE] must be EXACTLY one move from the LEGAL MOVES list provided
- [REASON] must be a single, concise sentence
- Do not add any other text before or after these tokens"""


# ── API call with 3-retry logic ───────────────────────────────────────────────

def ask_claude_with_retry(position_context: str) -> str:
    """
    Send position to Claude API with 3-retry logic and exponential backoff.
    Returns the raw text response from the model.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    print(f"[WHITE] API Key present: {bool(api_key)}", file=sys.stderr)
    print(f"[WHITE] API URL: {API_URL}", file=sys.stderr)
    print(f"[WHITE] Model: {MODEL}", file=sys.stderr)

    payload = {
        "model": MODEL,
        "max_tokens": 200,
        "system": WHITE_SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": position_context
            }
        ]
    }

    data = json.dumps(payload).encode("utf-8")

    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                API_URL,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=45) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                # Extract text from content blocks
                for block in body.get("content", []):
                    if block.get("type") == "text":
                        return block["text"].strip()
                return ""

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[WHITE API ERROR {e.code}] Attempt {attempt + 1}/{MAX_RETRIES}: {err_body}", file=sys.stderr)

        except urllib.error.URLError as e:
            print(f"[WHITE API CONNECTION ERROR] Attempt {attempt + 1}/{MAX_RETRIES}: {e.reason}", file=sys.stderr)

        except TimeoutError:
            print(f"[WHITE API TIMEOUT] Attempt {attempt + 1}/{MAX_RETRIES}", file=sys.stderr)

        except Exception as e:
            print(f"[WHITE API ERROR] Attempt {attempt + 1}/{MAX_RETRIES}: {type(e).__name__}: {e}", file=sys.stderr)

        # Exponential backoff before retry
        if attempt < MAX_RETRIES - 1:
            wait_time = RETRY_DELAY_BASE * (2 ** attempt)  # 0.5s, 1s, 2s
            print(f"[WHITE] Waiting {wait_time}s before retry...", file=sys.stderr)
            time.sleep(wait_time)

    print("[WHITE] All retries exhausted", file=sys.stderr)
    return ""


# ── Long-term memory retrieval ────────────────────────────────────────────────

def retrieve_lessons(color: str, fen: str) -> str:
    """
    Retrieve relevant lessons from long-term memory.
    Uses unified memory_manager (mem0 → JSON fallback).
    If memory_manager import fails entirely, tries direct JSON fallback.
    Has a 5-second timeout to prevent hanging.
    """
    import threading

    result = {"lessons": ""}
    error_occurred = {"value": False}

    def _fetch():
        try:
            from engine.memory_manager import retrieve_relevant_lessons
            lessons = retrieve_relevant_lessons(color, fen)
            result["lessons"] = lessons
        except Exception as e:
            error_occurred["value"] = True
            print(f"[WHITE] Memory manager failed: {e} — trying direct JSON fallback", file=sys.stderr)

    # Run with timeout to prevent hanging
    thread = threading.Thread(target=_fetch, daemon=True)
    thread.start()
    thread.join(timeout=5.0)

    if thread.is_alive():
        print("[WHITE] Memory retrieval timed out after 5s — using fallback", file=sys.stderr)
        error_occurred["value"] = True

    if not error_occurred["value"] and result["lessons"]:
        print(f"[WHITE] Retrieved lessons from memory manager", file=sys.stderr)
        return result["lessons"]

    # Direct fallback: read JSON file manually
    try:
        from pathlib import Path
        import json
        fallback_path = Path(__file__).parent.parent.parent.parent / "backend" / "data" / "fallback_lessons.json"
        if fallback_path.exists():
            with open(fallback_path, "r", encoding="utf-8") as f:
                store = json.load(f)
            user_id = f"{color}_player_v1"
            entries = store.get(user_id, [])
            if entries:
                recent = [e["lesson"] for e in entries[-5:]]
                lessons = "\n".join([f"- {lesson}" for lesson in recent])
                print(f"[WHITE] Loaded {len(recent)} lessons from JSON fallback", file=sys.stderr)
                return lessons
    except Exception as e2:
        print(f"[WHITE] JSON fallback also failed: {e2}", file=sys.stderr)

    return ""


# ── Parse model response ──────────────────────────────────────────────────────

def parse_model_response(response: str, legal_move_strs: set) -> tuple[str, str] | None:
    """
    Extract [MOVE] and [REASON] from model output using token format.
    Validates that the chosen move is actually legal.
    Returns (move_str, reason) or None if parsing fails.
    """
    chosen_move = None
    reason = "No reason provided"

    lines = response.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line == "[MOVE]":
            if i + 1 < len(lines):
                chosen_move = lines[i + 1].strip()
        elif line == "[REASON]":
            if i + 1 < len(lines):
                reason = lines[i + 1].strip()
        i += 1

    if not chosen_move:
        print(f"[PARSE ERROR] Could not find [MOVE] in response:\n{response}", file=sys.stderr)
        return None

    if chosen_move not in legal_move_strs:
        print(f"[INVALID MOVE] Model chose '{chosen_move}' which is not in legal moves", file=sys.stderr)
        # Try to find a close match (model sometimes adds extra chars)
        for legal in legal_move_strs:
            if legal.startswith(chosen_move[:4]):
                print(f"[FALLBACK] Using '{legal}' instead", file=sys.stderr)
                return legal, reason
        return None

    return chosen_move, reason


# ── Fallback: best deterministic move ────────────────────────────────────────

def deterministic_fallback(legal_moves: list, board: list) -> tuple[str, str]:
    """
    If the API call fails, pick the best move using simple heuristics.
    Priority: checkmate > capture > check > center > any legal move.
    """
    from engine.validate_move import simulate_move, in_check
    from engine.board import save_game_state, load_game_state
    import copy

    piece_vals = {"Q": 9, "R": 5, "B": 3, "N": 3, "P": 1,
                  "q": 9, "r": 5, "b": 3, "n": 3, "p": 1}

    best_move = legal_moves[0]
    best_score = -999

    state = load_game_state()

    for move in legal_moves:
        score = 0
        fr_r = 8 - int(move["from_sq"][1])
        fr_c = ord(move["from_sq"][0]) - ord("a")
        to_r = 8 - int(move["to_sq"][1])
        to_c = ord(move["to_sq"][0]) - ord("a")

        new_board = simulate_move(board, fr_r, fr_c, to_r, to_c)

        if in_check(new_board, "black"):
            score += 10
        if move.get("capture"):
            score += piece_vals.get(move["capture"], 0) * 10
        if move.get("special") in ("castling_kingside", "castling_queenside"):
            score += 15
        if move["to_sq"] in ("e4", "d4", "e5", "d5"):
            score += 5

        if score > best_score:
            best_score = score
            best_move = move

    return best_move["move_str"], f"Fallback: best available move (API unavailable)"


# ── Main ──────────────────────────────────────────────────────────────────────

def choose_and_apply() -> None:
    state = load_game_state()

    if state["turn"] != "white":
        print("NOT_MY_TURN")
        return

    if state["status"] in ("checkmate", "stalemate", "draw"):
        print("GAME_OVER")
        return

    board = state["board"]
    legal_moves = generate_all_legal_moves("white")

    if not legal_moves:
        print("NO_LEGAL_MOVES")
        return

    legal_move_strs = {m["move_str"] for m in legal_moves}

    # ── Retrieve lessons from long-term memory ────────────────────────────────
    fen = state_to_fen(state)
    print(f"[WHITE] Retrieving lessons from memory...", file=sys.stderr)
    ltm_lessons = retrieve_lessons("white", fen)

    # ── Build position context with LTM and ask Claude ───────────────────────
    position_context = build_position_context(state, legal_moves, ltm_lessons)
    print(f"[WHITE] Thinking about position (move {state['fullmove_number']})...", file=sys.stderr)

    raw_response = ask_claude_with_retry(position_context)

    if raw_response:
        parsed = parse_model_response(raw_response, legal_move_strs)
    else:
        parsed = None

    # ── Fallback if API failed or response was unparseable ────────────────────
    if not parsed:
        print("[WHITE] API failed — using deterministic fallback", file=sys.stderr)
        chosen_str, reason = deterministic_fallback(legal_moves, board)
    else:
        chosen_str, reason = parsed

    # ── Apply the move ────────────────────────────────────────────────────────
    result = apply_move(chosen_str)

    if result["status"] != "ok":
        print(f"[WHITE] Move {chosen_str} rejected: {result.get('reason')} — trying fallback", file=sys.stderr)
        chosen_str, reason = deterministic_fallback(legal_moves, board)
        result = apply_move(chosen_str)

    # ── Output ────────────────────────────────────────────────────────────────
    print(f"WHITE_MOVE: {chosen_str}")
    print(f"REASON: {reason}")

    game_status = result.get("game_status", "active")
    if game_status == "checkmate":
        print("RESULT: White wins by checkmate!")
    elif game_status == "stalemate":
        print("RESULT: Stalemate — draw!")
    elif game_status == "check":
        print("STATUS: Black is in check!")


def state_to_fen(state: dict) -> str:
    """Convert game state to FEN string for memory lookup."""
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

    position = "/".join(ranks)
    fen = f"{position} {state['turn']} "

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
    fen += str(state.get("en_passant") or "-")
    fen += f" {state.get('halfmove_clock', 0)} {state.get('fullmove_number', 1)}"

    return fen


if __name__ == "__main__":
    choose_and_apply()
