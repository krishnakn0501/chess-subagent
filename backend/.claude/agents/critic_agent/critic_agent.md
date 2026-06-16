# Critic Agent Definition

## Purpose
The Critic Agent analyzes chess moves and provides structured feedback to enable self-improvement in the multi-agent chess loop.

## Responsibilities
- Evaluate move quality based on win probability delta
- Extract insights from Stockfish's Principal Variation (PV) line
- Generate actionable lessons for player agents
- Support long-term memory integration via mem0

## Configuration
- **API Key**: `CRITIC_AGENT_API_KEY`
- **API URL**: `CRITIC_API_URL` (defaults to DashScope)
- **Model**: `CRITIC_MODEL` (defaults to qwen3.7-max)
- **Retry Logic**: 3 retries with exponential backoff

## Output Format
TOON (Token-Oriented Object Notation) — single pipe-delimited line:

sentiment|<POSITIVE|NEGATIVE|NEUTRAL>|explanation|<tactical breakdown>|lesson|<actionable takeaway>

Example:
sentiment|POSITIVE|explanation|Clear tactical breakdown referencing PV line|lesson|Concise actionable takeaway

## Integration Points
- Receives: FEN_before, FEN_after, win_probabilities, pv_line, move_details
- Called by: Orchestrator after each move is applied
- Stores lessons to: Memory Manager (player_color profiles) via TOON parse
- Lessons saved when sentiment == POSITIVE or NEGATIVE
- Broadcasts critic_update via WebSocket with move, color, and lesson correlation
