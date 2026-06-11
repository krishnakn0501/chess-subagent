"""
WebSocket Connection Manager for real-time game state broadcasting.

Manages multiple concurrent WebSocket connections and provides broadcast
capabilities for pushing game state updates to all connected frontend clients.
"""

import asyncio
import json
from typing import Any
from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """
    Manages WebSocket connections for real-time game state streaming.

    Thread-safe implementation using asyncio.Lock for connection pool management.
    Automatically handles disconnection cleanup during broadcasts.
    """

    def __init__(self) -> None:
        """Initialize empty connection pool."""
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """
        Accept and track a new WebSocket connection.

        Args:
            websocket: The FastAPI WebSocket instance to connect.
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a closed connection from the tracking pool.

        Args:
            websocket: The WebSocket instance to remove.
        """
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast_game_state(self, payload: dict[str, Any]) -> None:
        """
        Send JSON payload to all connected clients.

        Automatically detects and removes dead connections during broadcast.

        Args:
            payload: Dictionary to serialize and broadcast as JSON.
        """
        serialized = json.dumps(payload)
        dead_connections: list[WebSocket] = []

        for connection in self.active_connections:
            try:
                await connection.send_text(serialized)
            except WebSocketDisconnect:
                dead_connections.append(connection)
            except Exception:
                # Catch any other send errors (network issues, etc.)
                dead_connections.append(connection)

        # Clean up disconnected sockets
        if dead_connections:
            async with self._lock:
                for conn in dead_connections:
                    if conn in self.active_connections:
                        self.active_connections.remove(conn)

    async def broadcast_json(self, payload: dict[str, Any]) -> None:
        """
        Send JSON payload using WebSocket's native send_json method.

        Args:
            payload: Dictionary to send as JSON.
        """
        dead_connections: list[WebSocket] = []

        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except WebSocketDisconnect:
                dead_connections.append(connection)
            except Exception:
                dead_connections.append(connection)

        if dead_connections:
            async with self._lock:
                for conn in dead_connections:
                    if conn in self.active_connections:
                        self.active_connections.remove(conn)

    def get_connection_count(self) -> int:
        """
        Get the current number of active WebSocket connections.

        Returns:
            Integer count of connected clients.
        """
        return len(self.active_connections)

    async def is_connected(self) -> bool:
        """
        Check if there are any active connections.

        Returns:
            True if at least one client is connected.
        """
        async with self._lock:
            return len(self.active_connections) > 0
