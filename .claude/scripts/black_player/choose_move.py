"""
scripts/black-player/choose_move.py

Black subagent's decision-making entry point — AI powered.

The model receives:
  - The current board (visual + piece inventory)
  - All legal moves available
  - Game history so far
  - Its strategic identity (dynamic, Sicilian, counterattacking)

It responds with a chosen move and reason. No hardcoded book. No static scores.
Every decision is made by Claude reasoning about the actual position.

Usage:
  python3 scripts/black-player/choose_move.py
"""

import sys
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from board import load_game_state, render_board
from get_legal_moves import generate_all_legal_moves
from apply_move import apply_move

API_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com") + "/v1/messages"
MODEL   = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


# ── Board context builder ─────────────────────────────────────────────────────

def build_position_context(state: dict, legal_moves: list) -> str:
    """Build a rich text description of the position for the model."""
    board = state["board"]
    history = state.get("move_history", [])
    move_num = state.get("fullmove_number", 1)
    status = state.get("status", "active")
    castling = state.get("castling", {})
    en_passant = state.get("en_passant")

    board_str = render_board(board, use_unicode=False)

    recent = history[-10:] if len(history) > 10 else history
    history_str = ""
    for m in recent:
        if m["color"] == "white":
            history_str += f"{m['fullmove']}. {m['move']} "
        else:
            history_str += f"{m['move']}  "

    piece_vals = {"Q": 9, "R": 5, "B": 3, "N": 3, "P": 1,
                  "q": 9, "r": 5, "b": 3, "n": 3, "p": 1}
    white_mat = sum(piece_vals.get(p, 0) for row in board for p in row if p.isupper())
    black_mat = sum(piece_vals.get(p, 0) for row in board for p in row if p.islower())
    mat_str = f"White: {white_mat}pts  Black: {black_mat}pts  Delta: {black_mat - white_mat:+d} (Black perspective)"

    castle_str = []
    if castling.get("black_kingside"):  castle_str.append("O-O available")
    if castling.get("black_queenside"): castle_str.append("O-O-O available")
    if not castle_str: castle_str = ["no castling rights remaining"]

    # What was White's last move (threat awareness)
    white_moves = [m for m in history if m["color"] == "white"]
    last_white = f"White just played: {white_moves[-1]['move']}" if white_moves else "Game just started"

    move_list = ", ".join(m["move_str"] for m in legal_moves)

    return f"""== CHESS POSITION — MOVE {move_num} (BLACK TO PLAY) ==

BOARD (White=UPPERCASE  Black=lowercase  .=empty):
{board_str}

MATERIAL: {mat_str}
GAME PHASE: {"Opening (moves 1-12)" if move_num <= 12 else "Middlegame (moves 13-30)" if move_num <= 30 else "Endgame"}
STATUS: {status}
EN PASSANT TARGET: {en_passant or "none"}
BLACK CASTLING: {", ".join(castle_str)}
{last_white}
RECENT MOVES: {history_str.strip() or "Game just started"}

LEGAL MOVES FOR BLACK ({len(legal_moves)} total):
{move_list}"""


# ── System prompt for Black ───────────────────────────────────────────────────

BLACK_SYSTEM_PROMPT = """You are the Black chess player in a game against a White AI opponent.

YOUR IDENTITY & STYLE:
- You play dynamic, counterattacking chess — never passive
- Opening preference: Sicilian Defence (c5 vs e4), King's Indian (Nf6+g6 vs d4)
- Middlegame: seek imbalances, launch queenside pawn storms, look for tactical shots
- If behind: complicate the position, seek perpetual check or stalemate traps
- If ahead: simplify to a won endgame

YOUR DECISION PROCESS — think through these in order:
1. Am I in check? If yes, resolve it first (move King, block, or capture attacker)
2. Can I checkmate or force checkmate in 1-2 moves?
3. Can I win material without losing more? (captures, forks, discovered attacks)
4. What threat did White just make — and can I counter-attack instead of just defending?
5. Can I open files toward White's King?
6. Does castling or a pawn advance improve my position?

MOVE FORMAT — you must respond with ONLY this, nothing else:
CHOSEN_MOVE: <move_in_algebraic_notation>
REASON: <one clear sentence explaining your strategic thinking>

RULES:
- CHOSEN_MOVE must be EXACTLY one move from the LEGAL MOVES list provided
- Do not explain your thinking beyond the REASON line
- Do not add any other text before or after the two lines"""


# ── Claude API call ───────────────────────────────────────────────────────────

def ask_claude(position_context: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    print(f"[BLACK] API Key present: {bool(api_key)}", file=sys.stderr)
    print(f"[BLACK] API URL: {API_URL}", file=sys.stderr)
    print(f"[BLACK] Model: {MODEL}", file=sys.stderr)

    payload = {
        "model": MODEL,
        "max_tokens": 200,
        "system": BLACK_SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": position_context
            }
        ]
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            for block in body.get("content", []):
                if block.get("type") == "text":
                    return block["text"].strip()
            return ""
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[API ERROR {e.code}]: {err_body}", file=sys.stderr)
        print(f"[API ERROR] Request URL: {API_URL}", file=sys.stderr)
        print(f"[API ERROR] Model: {MODEL}", file=sys.stderr)
        return ""
    except urllib.error.URLError as e:
        print(f"[API CONNECTION ERROR]: {e.reason}", file=sys.stderr)
        return ""
    except TimeoutError:
        print(f"[API TIMEOUT]: Request timed out after 30 seconds", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"[API ERROR]: {type(e).__name__}: {e}", file=sys.stderr)
        return ""


# ── Parse model response ──────────────────────────────────────────────────────

def parse_model_response(response: str, legal_move_strs: set) -> tuple[str, str] | None:
    chosen_move = None
    reason = "No reason provided"

    for line in response.splitlines():
        line = line.strip()
        if line.startswith("CHOSEN_MOVE:"):
            chosen_move = line.split(":", 1)[1].strip()
        elif line.startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()

    if not chosen_move:
        print(f"[PARSE ERROR] No CHOSEN_MOVE in response:\n{response}", file=sys.stderr)
        return None

    if chosen_move not in legal_move_strs:
        print(f"[INVALID MOVE] '{chosen_move}' not in legal moves", file=sys.stderr)
        for legal in legal_move_strs:
            if legal.startswith(chosen_move[:4]):
                print(f"[FALLBACK] Using '{legal}' instead", file=sys.stderr)
                return legal, reason
        return None

    return chosen_move, reason


# ── Fallback: best deterministic move ────────────────────────────────────────

def deterministic_fallback(legal_moves: list, board: list) -> tuple[str, str]:
    from validate_move import simulate_move, in_check

    piece_vals = {"Q": 9, "R": 5, "B": 3, "N": 3, "P": 1,
                  "q": 9, "r": 5, "b": 3, "n": 3, "p": 1}

    best_move = legal_moves[0]
    best_score = -999

    for move in legal_moves:
        score = 0
        fr_r = 8 - int(move["from_sq"][1])
        fr_c = ord(move["from_sq"][0]) - ord("a")
        to_r = 8 - int(move["to_sq"][1])
        to_c = ord(move["to_sq"][0]) - ord("a")

        new_board = simulate_move(board, fr_r, fr_c, to_r, to_c)

        if in_check(new_board, "white"):
            score += 10
        if move.get("capture"):
            score += piece_vals.get(move["capture"], 0) * 10
        if move.get("special") in ("castling_kingside", "castling_queenside"):
            score += 15
        if move["to_sq"] in ("e5", "d5", "e4", "d4"):
            score += 5

        if score > best_score:
            best_score = score
            best_move = move

    return best_move["move_str"], "Fallback: best available move (API unavailable)"


# ── Main ──────────────────────────────────────────────────────────────────────

def choose_and_apply() -> None:
    state = load_game_state()

    if state["turn"] != "black":
        print("NOT_MY_TURN")
        return

    if state["status"] in ("checkmate", "stalemate", "draw"):
        print("GAME_OVER")
        return

    board = state["board"]
    legal_moves = generate_all_legal_moves("black")

    if not legal_moves:
        print("NO_LEGAL_MOVES")
        return

    legal_move_strs = {m["move_str"] for m in legal_moves}

    # ── Build position context and ask Claude ─────────────────────────────────
    position_context = build_position_context(state, legal_moves)
    print(f"[BLACK] Thinking about position (move {state['fullmove_number']})...", file=sys.stderr)

    raw_response = ask_claude(position_context)

    if raw_response:
        parsed = parse_model_response(raw_response, legal_move_strs)
    else:
        parsed = None

    if not parsed:
        print("[BLACK] API failed — using deterministic fallback", file=sys.stderr)
        chosen_str, reason = deterministic_fallback(legal_moves, board)
    else:
        chosen_str, reason = parsed

    # ── Apply the move ────────────────────────────────────────────────────────
    result = apply_move(chosen_str)

    if result["status"] != "ok":
        print(f"[BLACK] Move {chosen_str} rejected: {result.get('reason')} — trying fallback", file=sys.stderr)
        chosen_str, reason = deterministic_fallback(legal_moves, board)
        result = apply_move(chosen_str)

    # ── Output ────────────────────────────────────────────────────────────────
    print(f"BLACK_MOVE: {chosen_str}")
    print(f"REASON: {reason}")

    game_status = result.get("game_status", "active")
    if game_status == "checkmate":
        print("RESULT: Black wins by checkmate!")
    elif game_status == "stalemate":
        print("RESULT: Stalemate — draw!")
    elif game_status == "check":
        print("STATUS: White is in check!")


if __name__ == "__main__":
    choose_and_apply()

    