"""
orchestrator.py — Automated game execution loop between White and Black agents.

Controls the full game flow by:
1. Running agent subprocesses to choose moves
2. Broadcasting game state updates via WebSocket
3. Managing start/pause/stop/reset states
4. Detecting game-over conditions

All paths to .claude/scripts/ are resolved from project root.
"""

import asyncio
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
    Controls automated game execution between White and Black agents.

    Manages the game loop, agent subprocess execution, and broadcast coordination.
    All file paths use PROJECT_ROOT resolution for .claude access.
    """

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
        self.agent_timeout = 60.0  # Seconds timeout for agent subprocesses

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
            "state": state
        })
        return state

    async def step_one_move(self) -> dict[str, Any]:
        """Execute single move by current player's agent."""
        state = load_game_state()

        if state["status"] in ("checkmate", "stalemate", "draw"):
            return {
                "success": False,
                "error": "Game already over"
            }

        turn = state.get("turn", "white")
        result = await self._execute_agent(turn)

        new_state = load_game_state()

        await self.manager.broadcast_json({
            "type": "move_complete",
            "state": new_state,
            "agent_output": result
        })

        return result

    async def _game_loop(self) -> None:
        """Main automated game loop."""
        try:
            while self._running:
                if self._paused:
                    await asyncio.sleep(0.5)
                    continue

                state = load_game_state()

                if state["status"] in ("checkmate", "stalemate", "draw"):
                    self._running = False
                    break

                turn = state["turn"]
                result = await self._execute_agent(turn)

                # Debug block: show agent crash details
                if not result.get("success"):
                    print("\n" + "="*40)
                    print(f"[ORCHESTRATOR] AGENT CRASHED ({turn.upper()})")
                    print(f"Error Details:\n{result.get('error')}")
                    print("="*40 + "\n")
                    # Pause the game so it doesn't infinite loop the error
                    self._paused = True

                # Broadcast updated state
                new_state = load_game_state()
                await self.manager.broadcast_json({
                    "type": "move_complete",
                    "state": new_state,
                    "agent_output": result
                })

                await asyncio.sleep(self.move_delay)
        except Exception as e:
            self._running = False
            await self.manager.broadcast_json({
                "type": "error",
                "message": f"Game loop error: {str(e)}"
            })

    async def _execute_agent(self, color: str) -> dict[str, Any]:
        """
        Run the appropriate agent script as a background thread subprocess.
        """
        agent_script = self.project_root / ".claude" / "scripts" / f"{color}_player" / "choose_move.py"

        scripts_path = self.project_root / ".claude" / "scripts"
        engine_path = self.project_root / "backend" / "app" / "engine"
        existing_path = os.environ.get("PYTHONPATH", "")
        path_sep = os.pathsep
        pythonpath = f"{scripts_path}{path_sep}{engine_path}"
        if existing_path:
            pythonpath = f"{existing_path}{path_sep}{pythonpath}"
        env = {**os.environ, "PYTHONPATH": pythonpath}

        print(f"\n[ORCHESTRATOR] Waking up {color.upper()} agent...")
        print(f"[ORCHESTRATOR] Target script: {agent_script}")
        print(f"[ORCHESTRATOR] Environment check:")
        print(f"  - ANTHROPIC_API_KEY: {'SET' if env.get('ANTHROPIC_API_KEY') else 'NOT SET'}")
        print(f"  - ANTHROPIC_BASE_URL: {env.get('ANTHROPIC_BASE_URL', 'NOT SET')}")
        print(f"  - ANTHROPIC_MODEL: {env.get('ANTHROPIC_MODEL', 'NOT SET')}")

        try:
            # Wrap the standard subprocess in a synchronous function
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

            print(f"[ORCHESTRATOR] Spawning process in background thread...")
            
            # Execute it safely off the main event loop
            process = await asyncio.to_thread(run_script)

            if process.returncode != 0:
                print(f"[ORCHESTRATOR] {color.upper()} script failed with exit code {process.returncode}!")
                print(f"[ORCHESTRATOR] Error output:\n{process.stderr}")
            else:
                print(f"[ORCHESTRATOR] {color.upper()} completed a move successfully.")
                print(f"[ORCHESTRATOR] Agent output snippet: {process.stdout[:150]}")

            return {
                "success": process.returncode == 0,
                "output": process.stdout,
                "error": process.stderr
            }

        except subprocess.TimeoutExpired:
            print(f"[ORCHESTRATOR] CRITICAL: {color.upper()} agent timed out after {self.agent_timeout}s!")
            return {
                "success": False,
                "error": f"Agent execution timed out after {self.agent_timeout} seconds"
            }
        except Exception as e:
            # We use repr(e) so even silent errors like NotImplementedError show their name
            print(f"[ORCHESTRATOR] System error executing script: {repr(e)}")
            return {
                "success": False,
                "error": repr(e)
            }