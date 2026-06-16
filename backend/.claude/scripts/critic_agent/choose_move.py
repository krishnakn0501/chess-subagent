"""
scripts/critic_agent/choose_move.py — Critic Agent move analysis.

Analyzes chess moves using LLM to generate structured feedback:
- Sentiment assessment (POSITIVE/NEGATIVE/NEUTRAL)
- Tactical explanation using PV line from Stockfish
- Actionable lessons for long-term memory storage

Features:
- 3-retry logic with exponential backoff for all API calls
- Intelligent use of Principal Variation in explanations
- Robust error handling and graceful degradation

Usage:
    python scripts/critic_agent/choose_move.py --fen-before "..." --fen-after "..."
                                             --prob-before 50.0 --prob-after 55.0
                                             --move e2e4 --color white

Environment Variables:
    CRITIC_AGENT_API_KEY - API key for Critic service
    CRITIC_API_URL - Endpoint URL (defaults to DashScope)
    CRITIC_MODEL - Model name (defaults to qwen3.7-max)
"""

import sys
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
import argparse


# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / ".." / ".." / "backend" / "app"))
sys.path.insert(0, str(Path(__file__).parent))

API_URL = os.environ.get("CRITIC_API_URL", "https://dashscope-intl.aliyuncs.com/apps/anthropic") + "/v1/messages"
MODEL = os.environ.get("CRITIC_MODEL", "qwen3.7-max")


# ==========================================
# System Prompt for Critic Agent
# ==========================================

CRITIC_SYSTEM_PROMPT = """You are a Chess Critic Agent specializing in analyzing moves and generating actionable feedback for self-improving AI agents.

YOUR TASK:
Analyze a chess move based on win probability delta and Stockfish's Principal Variation (PV) line. Classify the move quality and extract strategic lessons.

EVALUATION GUIDELINES:

SENTIMENT CLASSIFICATION:
- POSITIVE: Move improves position (+5% win prob or better), follows sound strategy, or achieves tactical advantage
- NEGATIVE: Move worsens position significantly (-10% win prob or worse), commits blunder, or misses clear opportunity
- NEUTRAL: Positional equilibrium maintained, minor adjustments, opening preparation

ANALYSIS PROCESS:
1. Assess probability delta: new_prob - old_prob for active player
2. Extract key tactics from PV line if available
3. Identify what made the move good/bad/neutral
4. Formulate concise, actionable lesson

PV LINE USAGE:
- Reference specific sequences when they explain the evaluation change
- Use format: "Stockfish predicts [sequence] revealing that..."
- For mate scores: mention forced mate sequence clearly

OUTPUT FORMAT REQUIREMENTS:
Respond with EXACTLY this single-line TOON format — nothing else:
sentiment|<POSITIVE|NEGATIVE|NEUTRAL>|explanation|<tactical breakdown referencing PV or position>|lesson|<concise actionable takeaway>

Rules:
- Keys MUST be exactly: sentiment, explanation, lesson
- Values must NOT contain pipe characters
- Output exactly ONE line — nothing before or after
- Handle mate scores (forced mate = major event)
- If PV unavailable, focus on material/positional factors
"""


# ==========================================
# Build Analysis Context
# ==========================================

def build_context(
    fen_before: str,
    fen_after: str,
    move: str,
    color: str,
    prob_before: float,
    prob_after: float,
    pv_line: list,
    raw_score: str = ""
) -> str:
    """
    Build detailed context for Critic Agent analysis.

    Args:
        fen_before: FEN before move
        fen_after: FEN after move
        move: Move in UCI notation
        color: Player color ("white" or "black")
        prob_before: Win probability before move
        prob_after: Win probability after move
        pv_line: Principal variation from Stockfish
        raw_score: Raw score string from engine

    Returns:
        Formatted context string for LLM analysis
    """
    # Calculate probability delta
    if color == "white":
        delta = prob_after - prob_before
    else:
        delta = prob_before - prob_after  # Black perspective: their prob increases when white decreases

    delta_sign = "+" if delta >= 0 else ""

    # Format PV line for display
    pv_text = ""
    if pv_line and len(pv_line) > 0:
        pv_moves_str = ", ".join(pv_line[:6])  # First 6 moves
        pv_text = f"\n\nSTOCKFISH PV LINE (first 6 moves): [{pv_moves_str}]"
        if len(pv_line) > 6:
            pv_text += f"... ({len(pv_line)} total moves predicted)"

    # Parse FEN pieces for quick reference
    before_pieces = fen_before.split()[0][:30]
    after_pieces = fen_after.split()[0][:30]

    context = f"""== CHESS MOVE ANALYSIS ==

TURN: {color.upper()}
MOVE: {move.upper()}
RAW SCORE: {raw_score or "N/A"}

PROBABILITY ANALYSIS:
- Before: {prob_before}%
- After: {prob_after}%
- Delta: {delta_sign}{delta:.1f}% ({color}'s perspective)

BEFORE POSITION: {before_pieces}...
AFTER POSITION: {after_pieces}...{pv_text}

INSTRUCTIONS:
Analyze this move considering:
1. The probability delta indicates significant positional change
2. The PV line shows Stockfish's predicted continuation (if any)
3. Determine if the move was strategically sound or a mistake
4. Extract a reusable lesson for future similar positions

Remember: Focus on patterns that can be recognized in future games."""

    return context


# ==========================================
# API Call with Retry Logic
# ==========================================

def ask_critic_api(context: str) -> str:
    """
    Send analysis request to Critic API with 3-retry logic.

    Args:
        context: Analysis context string.

    Returns:
        Raw API response text or empty string on failure.
    """
    api_key = os.environ.get("CRITIC_AGENT_API_KEY", "")

    print(f"[Critic] API Key present: {bool(api_key)}", file=sys.stderr)
    print(f"[Critic] API URL: {API_URL}", file=sys.stderr)
    print(f"[Critic] Model: {MODEL}", file=sys.stderr)

    payload = {
        "model": MODEL,
        "max_tokens": 300,
        "system": CRITIC_SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": context
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
            "x-api-key": api_key,
        },
        method="POST"
    )

    MAX_RETRIES = 3

    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                # Extract text from content blocks
                for block in body.get("content", []):
                    if block.get("type") == "text":
                        return block["text"].strip()
                return ""

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[Critic API ERROR {e.code}] Attempt {attempt + 1}/{MAX_RETRIES}: {err_body}", file=sys.stderr)

        except urllib.error.URLError as e:
            print(f"[Critic API CONNECTION ERROR] Attempt {attempt + 1}/{MAX_RETRIES}: {e.reason}", file=sys.stderr)

        except TimeoutError:
            print(f"[Critic API TIMEOUT] Attempt {attempt + 1}/{MAX_RETRIES}", file=sys.stderr)

        except Exception as e:
            print(f"[Critic API ERROR] Attempt {attempt + 1}/{MAX_RETRIES}: {type(e).__name__}: {e}", file=sys.stderr)

        # Exponential backoff before retry
        if attempt < MAX_RETRIES - 1:
            wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
            print(f"[Critic] Waiting {wait_time}s before retry...", file=sys.stderr)
            import time
            time.sleep(wait_time)

    print("[Critic] All retries exhausted", file=sys.stderr)
    return ""


# ==========================================
# Parse Response
# ==========================================

def parse_toon(text: str) -> dict:
    """
    Parse TOON (Token-Oriented Object Notation) — pipe-delimited key-value pairs.
    Format: key1|value1|key2|value2|key3|value3

    Args:
        text: Raw TOON string.

    Returns:
        Dictionary of key-value pairs, or empty dict on failure.
    """
    parts = text.strip().split("|")
    if len(parts) < 6 or len(parts) % 2 != 0:
        return {}
    return {parts[i]: parts[i + 1] for i in range(0, len(parts), 2)}


def parse_response(response: str) -> dict:
    """
    Parse Critic API response into a structured dictionary.

    Primary: TOON pipe-delimited format (sentiment|...|explanation|...|lesson|...)
    Fallback: [SENTIMENT]\n...\n[LESSON]\n... bracket tokens

    Args:
        response: Raw text response from API.

    Returns:
        Dictionary with sentiment, explanation, lesson keys.
    """
    default_result = {
        "sentiment": "NEUTRAL",
        "explanation": "Analysis unavailable due to service error",
        "lesson": "No lesson could be extracted at this time"
    }

    if not response:
        print("[Critic] Empty response received", file=sys.stderr)
        return default_result

    # ── 1. Try TOON first (what the system prompt instructs) ──
    toon_result = parse_toon(response)
    if toon_result and all(k in toon_result for k in ["sentiment", "explanation", "lesson"]):
        if toon_result["sentiment"].upper() in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
            toon_result["sentiment"] = toon_result["sentiment"].upper()
            print("[Critic] Parsed TOON format successfully", file=sys.stderr)
            return toon_result

    # ── 2. Fallback: bracket-token format ([SENTIMENT]/[LESSON]) ──
    lines = response.strip().splitlines()
    sentiment = "NEUTRAL"
    lesson = "No lesson extracted"
    explanation_from_body = ""

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line == "[SENTIMENT]" and i + 1 < len(lines):
            s = lines[i + 1].strip().upper()
            if s in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
                sentiment = s
            i += 2
        elif line == "[LESSON]" and i + 1 < len(lines):
            lesson = lines[i + 1].strip()
            i += 2
        else:
            # Collect non-marker lines for explanation fallback
            stripped = line.strip()
            if len(stripped) > 15 and not explanation_from_body:
                explanation_from_body = stripped
            i += 1

    # Use the collected explanation or fall back to lesson text
    explanation = explanation_from_body if explanation_from_body else lesson

    return {
        "sentiment": sentiment,
        "explanation": explanation,
        "lesson": lesson
    }


# ==========================================
# Main Entry Point
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Critic Agent - Analyze chess moves")
    parser.add_argument("--fen-before", required=True, help="FEN before move")
    parser.add_argument("--fen-after", required=True, help="FEN after move")
    parser.add_argument("--move", required=True, help="Move in UCI notation")
    parser.add_argument("--color", required=True, choices=["white", "black"], help="Player color")
    parser.add_argument("--prob-before", type=float, default=50.0, help="Win probability before")
    parser.add_argument("--prob-after", type=float, default=50.0, help="Win probability after")
    parser.add_argument("--pv-line", nargs="*", default=[], help="Principal variation moves")
    parser.add_argument("--raw-score", default="", help="Raw engine score")

    args = parser.parse_args()

    # Build context
    context = build_context(
        fen_before=args.fen_before,
        fen_after=args.fen_after,
        move=args.move,
        color=args.color,
        prob_before=args.prob_before,
        prob_after=args.prob_after,
        pv_line=args.pv_line,
        raw_score=args.raw_score
    )

    print(f"[Critic] Analyzing move: {args.move} by {args.color}", file=sys.stderr)

    # Call API
    raw_response = ask_critic_api(context)

    # Parse result and output as TOON (single pipe-delimited line)
    result = parse_response(raw_response)

    toon_output = f"sentiment|{result['sentiment']}|explanation|{result['explanation']}|lesson|{result['lesson']}"
    print(toon_output)


if __name__ == "__main__":
    main()
