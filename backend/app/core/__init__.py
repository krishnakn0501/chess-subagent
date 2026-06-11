"""
Core module for Chess Arena backend.

Contains configuration, path utilities, and WebSocket connection management.
"""

from .config import GameConfig, GameStatePaths, get_paths, get_config
from .connection import ConnectionManager

__all__ = ["GameConfig", "GameStatePaths", "ConnectionManager", "get_paths", "get_config"]
