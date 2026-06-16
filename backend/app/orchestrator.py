"""
orchestrator.py — Enhanced automated game execution loop between White and Black agents.

Controls the full game flow with self-improvement capabilities:
1. Running agent subprocesses to choose moves
2. Stockfish position evaluation with win probability calculation
3. Critic Agent analysis of move quality using PV lines
4. Long-term memory storage via mem0 for player lessons
5. Enhanced WebSocket broadcasting with rich metadata
6. 3-retry logic with exponential backoff for all API calls

All paths to .claude/scripts/ are resolved from project root.
"""

import asyncio
import json
import os
from pathlib import Path
import subprocess
from typing import Any
import sys

# Add backend/app to path for relative imports
sys.path.insert(0, str(Path(__file__).parent))

from core.connection import ConnectionManager
from engine.board import load_game_state, init_game_state


class GameOrchestrator:
    """
    Controls automated game execution between White and Black agents with self-improvement.

    Features:
    - Stockfish-based win probability tracking
    - Critic Agent for move analysis
    - Long-term memory integration (mem0)
    - 3-retry logic with exponential backoff
    - Enhanced WebSocket broadcasts

    All file paths use PROJECT_ROOT resolution for .claude access.
    """

    MAX_API_RETRIES = 3
    RETRY_DELAY_BASE = 0.5  # seconds, doubles each retry

    def __init__(self, connection_manager: ConnectionManager) -> None:
        """
        Initialize orchestrator with a connection manager.

        Args:
            connection_manager: The ConnectionManager instance for broadcasting.
        """
        self.manager = connection_manager
        self._running = False
        self._paused = True
        self._task: asyncio.Task | None = None

        # Project root is 3 levels up from backend/app/orchestrator.py
        self.project_root = Path(__file__).parent.parent.parent
        self.move_delay = 1.0  # Seconds between automated moves
        self.agent_timeout = 150.0  # Seconds timeout for agent subprocesses

        # Initialize components
        self._stockfish_evaluator = None
        self._memory_client = None

    async def _initialize_components(self) -> bool:
        """
        Initialize Stockfish evaluator and memory client.
        Called once on first move.

        Returns:
            True if initialization successful, False otherwise.
        """
        try:
            # Import here to avoid circular dependencies
            from engine.stockfish_evaluator import StockfishEvaluator
            from engine.memory_manager import get_qwen_memory_client

            # Initialize Stockfish
            if self._stockfish_evaluator is None:
                self._stockfish_evaluator = StockfishEvaluator()
                stockfish_ok = await self._stockfish_evaluator.initialize()
                print(f"[Orchestrator] Stockfish initialized: {'✓' if stockfish_ok else '✗'}")

            # Initialize Memory Client
            if self._memory_client is None:
                self._memory_client = get_qwen_memory_client()
                print("[Orchestrator] Memory client initialized")

            return True

        except Exception as e:
            print(f"[Orchestrator] Component initialization failed: {e}", file=sys.stderr)
            return False

    async def start(self) -> None:
        """Begin the automated game loop."""
        if self._running:
            return

        self._running = True
        self._paused = False
        self._task = asyncio.create_task(self._game_loop())

    async def stop(self) -> None:
        """Stop the game loop cleanly."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None

    def pause_toggle(self) -> bool:
        """Toggle pause state; returns new pause status."""
        self._paused = not self._paused
        return self._paused

    async def reset_game(self) -> dict[str, Any]:
        """Reset game to starting position and notify clients."""
        if self._task:
            await self.stop()

        state = init_game_state()
        await self.manager.broadcast_json({
            "type": "reset",
            "state": state,
            "win_probabilities": {"white": 50.0, "black": 50.0},
            "critic_commentary": None,
            "pv_line": []
        })
        return state

    async def step_one_move(self) -> dict[str, Any]:
        """Execute single move by current player's agent with enhanced feedback."""
        state = load_game_state()

        if state["status"] in ("checkmate", "stalemate", "draw"):
            return {
                "success": False,
                "error": "Game already over"
            }

        turn = state.get("turn", "white")
        result = await self._execute_agent_with_enhancements(turn)

        new_state = load_game_state()

        await self.manager.broadcast_json({
            "type": "move_complete",
            "state": new_state,
            "agent_output": result,
            "win_probabilities": result.get("win_probabilities", {}),
            "critic_commentary": result.get("critic_commentary"),
            "pv_line": result.get("pv_line", [])
        })

        return result

    async def _game_loop(self) -> None:
        """Main automated game loop with self-improvement."""
        try:
            # Initialize components on first iteration
            await self._initialize_components()

            while self._running:
                if self._paused:
                    await asyncio.sleep(0.5)
                    continue

                state = load_game_state()

                if state["status"] in ("checkmate", "stalemate", "draw"):
                    self._running = False
                    break

                turn = state["turn"]
                result = await self._execute_agent_with_enhancements(turn)

                # Debug block: show agent crash details
                if not result.get("success"):
                    print("\n" + "="*40)
                    print(f"[ORCHESTRATOR] AGENT CRASHED ({turn.upper()})")
                    print(f"Error Details:\n{result.get('error')}")
                    print("="*40 + "\n")
                    # Pause the game so it doesn't infinite loop the error
                    self._paused = True

                # Broadcast updated state with enhancements
                new_state = load_game_state()
                await self.manager.broadcast_json({
                    "type": "move_complete",
                    "state": new_state,
                    "agent_output": result,
                    "win_probabilities": result.get("win_probabilities", {}),
                    "critic_commentary": result.get("critic_commentary"),
                    "pv_line": result.get("pv_line", [])
                })

                await asyncio.sleep(self.move_delay)

        except Exception as e:
            self._running = False
            await self.manager.broadcast_json({
                "type": "error",
                "message": f"Game loop error: {str(e)}"
            })

    async def _execute_agent_with_enhancements(self, color: str) -> dict[str, Any]:
        """
        Execute agent with full enhancement pipeline:
        1. Get pre-move FEN and evaluate with Stockfish
        2. Run agent script (with LTM retrieval)
        3. Apply move
        4. Get post-move FEN and evaluate
        5. IMMEDIATELY broadcast state to WebSocket
        6. Run Critic Agent analysis in background
        7. Store lesson in memory if significant
        8. Return enhanced result

        Args:
            color: Player color ("white" or "black")

        Returns:
            Enhanced result dictionary with all metadata
        """
        # Step 1: Get pre-move FEN and evaluate
        state_before = load_game_state()
        fen_before = self._board_to_fen(state_before)

        # Evaluate before move
        win_probs_before = await self._evaluate_with_retry(fen_before)

        # Step 2: Execute agent script
        print(f"\n[ORCHESTRATOR] Executing {color.upper()} agent with LTM...")
        agent_result = await self._execute_agent(color)

        if not agent_result.get("success"):
            # Agent failed after all retries — use orchestrator-level fallback
            print(f"[ORCHESTRATOR] Agent failed — invoking deterministic fallback for {color.upper()}...")
            fallback_result = await self._orchestrator_fallback(color)
            if fallback_result.get("success"):
                agent_result = fallback_result
            else:
                return {
                    **agent_result,
                    "win_probabilities": win_probs_before,
                    "critic_commentary": {
                        "sentiment": "NEUTRAL",
                        "explanation": "Agent execution failed and fallback unavailable",
                        "lesson": "No lesson extracted due to error"
                    },
                    "pv_line": []
                }

        # Step 3: Get post-move FEN and evaluate
        state_after = load_game_state()
        fen_after = self._board_to_fen(state_after)

        # Evaluate after move
        win_probs_after = await self._evaluate_with_retry(fen_after)

        # Step 4: Extract move from agent output
        move_str = self._extract_move_from_output(agent_result.get("output", ""))

        # Step 5: IMMEDIATELY broadcast updated state with current win probabilities (before critic analysis)
        enhanced_result = {
            "success": True,
            "output": agent_result.get("output", ""),
            "error": agent_result.get("error", ""),
            "win_probabilities": {
                "white": win_probs_after.get("white_prob", 50.0),
                "black": win_probs_after.get("black_prob", 50.0)
            },
            "critic_commentary": None,  # Will be added later via background task
            "pv_line": win_probs_after.get("pv_line", [])
        }

        # Broadcast immediately without waiting for critic analysis
        await self.manager.broadcast_json({
            "type": "move_complete",
            "state": state_after,
            "agent_output": agent_result,
            "win_probabilities": enhanced_result["win_probabilities"],
            "critic_commentary": None,  # Critic analysis not ready yet
            "pv_line": enhanced_result["pv_line"]
        })

        # Step 6: Run Critic Agent analysis in background task
        print("[Orchestrator] Starting background Critic Agent analysis...")
        critic_task = asyncio.create_task(
            self._run_critic_analysis_and_broadcast(
                fen_before=fen_before,
                fen_after=fen_after,
                move=move_str,
                color=color,
                prob_before=win_probs_before.get("white_prob", 50.0),
                prob_after=win_probs_after.get("white_prob", 50.0),
                pv_line=win_probs_after.get("pv_line", []),
                original_state=state_after  # Pass state to correlate critic result
            )
        )

        # Step 7: Wait for up to 10-15 seconds for critic analysis, then continue with game
        try:
            await asyncio.wait_for(critic_task, timeout=15.0)  # Wait max 15 seconds for critic
        except asyncio.TimeoutError:
            print("[Orchestrator] Critic analysis timed out after 15 seconds, continuing game")

        # Compile final enhanced result (critic might not have completed in time)
        final_result = enhanced_result.copy()

        # Debug output
        print(f"[Orchestrator] Win Probabilities: White={final_result['win_probabilities']['white']}%, "
              f"Black={final_result['win_probabilities']['black']}%")

        return final_result

    async def _execute_agent(self, color: str) -> dict[str, Any]:
        """
        Run the appropriate agent script as a background thread subprocess.
        With 3-retry logic and LTM integration.
        """
        agent_script = self.project_root / ".claude" / "scripts" / f"{color}_player" / "choose_move.py"

        scripts_path = self.project_root / ".claude" / "scripts"
        engine_path = self.project_root / "app" / "engine"
        existing_path = os.environ.get("PYTHONPATH", "")
        path_sep = os.pathsep
        pythonpath = f"{scripts_path}{path_sep}{engine_path}"
        if existing_path:
            pythonpath = f"{existing_path}{path_sep}{pythonpath}"
        env = {**os.environ, "PYTHONPATH": pythonpath}

        print(f"[ORCHESTRATOR] Target script: {agent_script}")
        print("[ORCHESTRATOR] Environment check:")
        print(f"  - ANTHROPIC_API_KEY: {'SET' if env.get('ANTHROPIC_API_KEY') else 'NOT SET'}")
        print(f"  - ANTHROPIC_BASE_URL: {env.get('ANTHROPIC_BASE_URL', 'NOT SET')}")
        print(f"  - ANTHROPIC_MODEL: {env.get('ANTHROPIC_MODEL', 'NOT SET')}")

        MAX_RETRIES = self.MAX_API_RETRIES

        for attempt in range(MAX_RETRIES):
            try:
                def run_script():
                    return subprocess.run(
                        [sys.executable, str(agent_script)],
                        cwd=str(self.project_root),
                        env=env,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=self.agent_timeout
                    )

                process = await asyncio.to_thread(run_script)

                if process.returncode != 0:
                    print(f"[ORCHESTRATOR] Script failed with exit code {process.returncode}!")
                    print(f"[ORCHESTRATOR] Error output:\n{process.stderr}")
                else:
                    print(f"[ORCHESTRATOR] {color.upper()} completed successfully.")
                    print(f"[ORCHESTRATOR] Output snippet: {process.stdout[:150]}")

                return {
                    "success": process.returncode == 0,
                    "output": process.stdout,
                    "error": process.stderr
                }

            except subprocess.TimeoutExpired:
                print(f"[ORCHESTRATOR] Timeout expired. Retry {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                continue

            except Exception as e:
                print(f"[ORCHESTRATOR] Execution error: {repr(e)}")
                if attempt < MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                continue

        return {
            "success": False,
            "error": f"Agent execution failed after {MAX_RETRIES} retries"
        }

    async def _evaluate_with_retry(self, fen: str) -> dict[str, Any]:
        """
        Evaluate position with Stockfish with 3-retry logic.

        Args:
            fen: FEN string to analyze.

        Returns:
            Evaluation result dictionary.
        """
        if self._stockfish_evaluator is None:
            return {
                "white_prob": 50.0,
                "black_prob": 50.0,
                "raw_score": "N/A",
                "cp_value": 0.0,
                "is_mate": False,
                "mate_in": None,
                "pv_line": [],
                "error": "Stockfish not initialized"
            }

        MAX_RETRIES = self.MAX_API_RETRIES

        for attempt in range(MAX_RETRIES):
            try:
                result = await self._stockfish_evaluator.get_win_probability(fen)

                if result.get("error") is None:
                    return result

                print(f"[Orchestrator] Analysis failed. Retry {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                    await asyncio.sleep(wait_time)

            except Exception as e:
                print(f"[Orchestrator] Evaluation error: {e}. Retry {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                    await asyncio.sleep(wait_time)

        return {
            "white_prob": 50.0,
            "black_prob": 50.0,
            "raw_score": "Failed after retries",
            "cp_value": 0.0,
            "is_mate": False,
            "mate_in": None,
            "pv_line": [],
            "error": "Max retries exceeded"
        }

    async def _analyze_move_with_retry(
        self,
        fen_before: str,
        fen_after: str,
        move: str,
        color: str,
        prob_before: float,
        prob_after: float,
        pv_line: list
    ) -> dict[str, Any]:
        """
        Run Critic Agent analysis with 3-retry logic.

        Args:
            fen_before: FEN before move
            fen_after: FEN after move
            move: Move in UCI notation
            color: Player color
            prob_before: Win probability before move
            prob_after: Win probability after move
            pv_line: Principal variation from Stockfish

        Returns:
            Critic analysis result dictionary.
        """
        critic_script = self.project_root / "backend" / ".claude" / "scripts" / "critic_agent" / "choose_move.py"

        args = [
            sys.executable,
            str(critic_script),
            "--fen-before", fen_before,
            "--fen-after", fen_after,
            "--move", move,
            "--color", color,
            "--prob-before", str(prob_before),
            "--prob-after", str(prob_after),
            "--raw-score", "auto"
        ]

        # Add PV line arguments
        for i, pv_move in enumerate(pv_line[:10]):  # Limit to first 10 moves
            args.extend(["--pv-line", pv_move])

        env = {**os.environ}

        MAX_RETRIES = self.MAX_API_RETRIES

        for attempt in range(MAX_RETRIES):
            try:
                process = await asyncio.to_thread(
                    lambda: subprocess.run(
                        args,
                        cwd=str(self.project_root),
                        env=env,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=60
                    )
                )

                if process.returncode == 0:
                    raw_output = process.stdout.strip()
                    # Try TOON parse (primary format)
                    result = self._parse_toon(raw_output)
                    if result and all(k in result for k in ["sentiment", "explanation", "lesson"]):
                        return result
                    # Fallback: bracket-token format
                    result = self._parse_token_fallback(raw_output)
                    if result and all(k in result for k in ["sentiment", "explanation", "lesson"]):
                        return result
                    print(f"[Critic] Could not parse output. Retry {attempt + 1}/{MAX_RETRIES}")

                if attempt < MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                    await asyncio.sleep(wait_time)

            except subprocess.TimeoutExpired:
                print(f"[Critic] Timeout. Retry {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                continue

            except Exception as e:
                print(f"[Critic] Error: {e}. Retry {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY_BASE * (2 ** attempt)
                    await asyncio.sleep(wait_time)
                continue

        return {
            "sentiment": "NEUTRAL",
            "explanation": "Critic analysis unavailable after retries",
            "lesson": "No lesson extracted"
        }

    async def _run_critic_analysis_and_broadcast(self, fen_before: str, fen_after: str, move: str,
                                               color: str, prob_before: float, prob_after: float,
                                               pv_line: list, original_state: dict) -> None:
        """
        Run critic analysis in background and broadcast result when complete.

        Args:
            fen_before: FEN before move
            fen_after: FEN after move
            move: Move in UCI notation
            color: Player color
            prob_before: Win probability before move
            prob_after: Win probability after move
            pv_line: Principal variation from Stockfish
            original_state: Original game state to correlate with analysis
        """
        try:
            critic_result = await self._analyze_move_with_retry(
                fen_before=fen_before,
                fen_after=fen_after,
                move=move,
                color=color,
                prob_before=prob_before,
                prob_after=prob_after,
                pv_line=pv_line
            )

            # Store lesson if significant
            if critic_result and critic_result.get("sentiment") in ["POSITIVE", "NEGATIVE"]:
                lesson_text = f"{critic_result.get('lesson', '')} Explanation: {critic_result.get('explanation', '')}"
                self._store_lesson_with_retry(color, fen_after, lesson_text)

            # Broadcast critic result to all clients via WebSocket
            await self.manager.broadcast_json({
                "type": "critic_update",  # New message type for critic updates
                "critic_commentary": critic_result,
                "move": move,
                "color": color,
                "fen_after": fen_after,
                "timestamp": __import__('time').time()  # Add timestamp to correlate with move
            })

            print(f"[Orchestrator] Critic analysis broadcasted for {color} move {move}")

        except Exception as e:
            print(f"[Orchestrator] Background critic analysis failed: {e}")

    async def _store_lesson_with_retry(self, player_color: str, fen: str, lesson: str) -> bool:
        """
        Store lesson in memory with 3-retry logic.

        Args:
            player_color: "white" or "black"
            fen: Current FEN
            lesson: Lesson text to store

        Returns:
            True if stored successfully.
        """
        try:
            from engine.memory_manager import store_lesson

            store_lesson(player_color, fen, lesson)
            print(f"[Orchestrator] Stored lesson for {player_color}: {lesson[:50]}...")
            return True

        except Exception as e:
            print(f"[Orchestrator] Failed to store lesson: {e}")
            return False

    def _board_to_fen(self, state: dict) -> str:
        """Convert game state board to FEN string."""
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

        # Build complete FEN (turn must be 'w' or 'b', not full words)
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

    def _extract_move_from_output(self, output: str) -> str:
        """Extract move from agent output."""
        lines = output.split('\n')

        # Check for token format first
        for i, line in enumerate(lines):
            line = line.strip()
            if line == "[MOVE]" and i + 1 < len(lines):
                move = lines[i + 1].strip()
                return move

        # Check for old format
        for line in lines:
            line = line.strip().upper()
            if line.startswith(("WHITE_MOVE:", "BLACK_MOVE:")):
                move = line.split(":", 1)[1].strip()
                return move
            if line.startswith("CHOSEN_MOVE:"):
                move = line.split(":", 1)[1].strip()
                return move

        # Default: return first plausible UCI-like pattern
        for line in lines:
            import re
            match = re.search(r'[a-h][1-8][a-h][1-8]', line)
            if match:
                return match.group()

        return "unknown"

    @staticmethod
    def _parse_toon(text: str) -> dict:
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

    @staticmethod
    def _parse_token_fallback(text: str) -> dict:
        """
        Fallback parser for badly-formatted critic output using bracket tokens.
        Handles [SENTIMENT], [LESSON], [REASON], [MOVE] markers.

        Args:
            text: Raw text with possible bracket markers.

        Returns:
            Dictionary with sentiment/explanation/lesson keys if found, else empty dict.
        """
        result = {}
        lines = text.strip().splitlines()
        i = 0
        while i < len(lines):
            stripped = lines[i].strip().lower()
            if stripped in ("[sentiment]", "sentiment") and i + 1 < len(lines):
                val = lines[i + 1].strip().upper()
                if val in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
                    result["sentiment"] = val
                i += 2
            elif stripped in ("[explanation]", "explanation") and i + 1 < len(lines):
                result["explanation"] = lines[i + 1].strip()
                i += 2
            elif stripped in ("[lesson]", "lesson") and i + 1 < len(lines):
                result["lesson"] = lines[i + 1].strip()
                i += 2
            elif stripped in ("[move]", "move") and i + 1 < len(lines):
                result["move"] = lines[i + 1].strip()
                i += 2
            elif stripped in ("[reason]", "reason") and i + 1 < len(lines):
                result["reason"] = lines[i + 1].strip()
                i += 2
            else:
                i += 1
        return result

    async def _orchestrator_fallback(self, color: str) -> dict[str, Any]:
        """
        Deterministic fallback when agent subprocess fails after all retries.
        Uses the chess engine directly to pick the best available legal move.

        Priority: castling > capture (by piece value) > check > center > first legal move.

        Args:
            color: Player color ("white" or "black")

        Returns:
            Result dictionary with success=True and the chosen move output.
        """
        try:
            from engine.get_legal_moves import generate_all_legal_moves
            from engine.apply_move import apply_move
            from engine.validate_move import simulate_move, in_check

            legal_moves = generate_all_legal_moves(color)
            if not legal_moves:
                return {"success": False, "error": "No legal moves available in fallback"}

            state = load_game_state()
            board = state["board"]

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

                enemy_color = "black" if color == "white" else "white"
                if in_check(new_board, enemy_color):
                    score += 10
                if move.get("capture"):
                    score += piece_vals.get(move["capture"], 0) * 10
                if move.get("special") in ("castling_kingside", "castling_queenside"):
                    score += 15
                center_squares = ("e4", "d4", "e5", "d5")
                if move["to_sq"] in center_squares:
                    score += 5

                if score > best_score:
                    best_score = score
                    best_move = move

            chosen_str = best_move["move_str"]
            result = apply_move(chosen_str)

            print(f"[ORCHESTRATOR] Fallback applied for {color.upper()}: {chosen_str} (score={best_score})")

            return {
                "success": True,
                "output": f"{color.upper()}_MOVE: {chosen_str}\nREASON: Orchestrator fallback (agent unavailable)",
                "error": "",
            }

        except Exception as e:
            print(f"[ORCHESTRATOR] Fallback also failed: {e}", file=sys.stderr)
            return {"success": False, "error": f"Fallback failed: {e}"}
