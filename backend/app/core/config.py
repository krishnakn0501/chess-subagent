"""
Configuration and path utilities for the chess game backend.

All paths to .claude/ and backend/app/engine/ are resolved from the project root directory
to ensure correct file access regardless of where the backend is invoked from.
"""

from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class GameStatePaths:
    """
    Immutable container for all file paths used by the chess backend.

    Paths to .claude/ scripts and backend/app/engine/ modules are resolved from the project
    root to maintain compatibility with the agent execution system.
    """
    # Project root (two levels up from backend/app/)
    PROJECT_ROOT: Path

    @property
    def game_state_dir(self) -> Path:
        """Path to game_state/ directory containing current.json."""
        return self.PROJECT_ROOT / "game_state"

    @property
    def current_game_json(self) -> Path:
        """Path to current game state JSON file."""
        return self.game_state_dir / "current.json"

    @property
    def last_game_pgn(self) -> Path:
        """Path to last completed game PGN file."""
        return self.game_state_dir / "last_game.pgn"

    @property
    def claude_settings(self) -> Path:
        """Path to Claude Code settings file."""
        return self.PROJECT_ROOT / ".claude" / "settings.json"

    @property
    def white_agent_script(self) -> Path:
        """Path to White player move selection script."""
        return self.PROJECT_ROOT / ".claude" / "scripts" / "white_player" / "choose_move.py"

    @property
    def black_agent_script(self) -> Path:
        """Path to Black player move selection script."""
        return self.PROJECT_ROOT / ".claude" / "scripts" / "black_player" / "choose_move.py"


# Initialize with project root detection
# PROJECT_ROOT is 2 levels up from this file (backend/app/core/ -> project_root)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
PATHS = GameStatePaths(PROJECT_ROOT)


@dataclass
class GameConfig:
    """Tunable configuration parameters for the chess game."""

    # WebSocket settings
    max_websocket_connections: int = 100
    websocket_ping_interval: float = 30.0  # seconds

    # Game loop settings
    move_delay_seconds: float = 1.0  # delay between automated moves
    agent_timeout_seconds: float = 60.0  # timeout for agent subprocesses

    # Move generation limits
    max_moves_per_game: int = 200

    @classmethod
    def default(cls) -> "GameConfig":
        """Return default configuration instance."""
        return cls()


def get_paths() -> GameStatePaths:
    """Get the global GameStatePaths singleton."""
    return PATHS


def get_config() -> GameConfig:
    """Get a fresh GameConfig instance with defaults."""
    return GameConfig.default()
