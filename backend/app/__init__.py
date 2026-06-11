"""
Chess Arena Backend Application.

A FastAPI-based backend for the Claude Code Chess sub-agent game system.
Provides REST control endpoints and real-time WebSocket streaming.
"""

from .core import ConnectionManager, GameConfig, GameStatePaths, get_paths, get_config

__all__ = [
    "ConnectionManager",
    "GameConfig",
    "GameStatePaths",
    "get_paths",
    "get_config"
]
