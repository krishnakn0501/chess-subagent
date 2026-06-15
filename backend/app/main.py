"""
main.py — FastAPI entrypoint for Chess Arena backend.

Provides:
- REST control endpoints (/api/control)
- WebSocket streaming endpoint (/ws/game)
- Health/status monitoring
- Settings configuration endpoint (/api/settings)

All agent paths resolve from project root for .claude access.
"""

import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal, Any
from pathlib import Path
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure path resolution
PROJECT_ROOT = Path(__file__).parent.parent.parent

from app.core.connection import ConnectionManager
from app.core.config import get_paths, get_config
from app.orchestrator import GameOrchestrator
from app.engine.board import load_game_state, init_game_state


# Initialize FastAPI app
app = FastAPI(
    title="Claude Chess Arena API",
    description="Real-time chess game between AI sub-agents",
    version="1.0.0"
)

# CORS configuration for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
manager = ConnectionManager()
orchestrator = GameOrchestrator(manager)


# ── Request/Response Models ───────────────────────────────────────────────────

class ControlCommand(BaseModel):
    """Command model for /api/control endpoint."""
    command: Literal["start", "stop", "pause", "reset", "step"]
    payload: dict[str, Any] | None = None


class StatusResponse(BaseModel):
    """Health check response model."""
    status: str
    websocket_clients: int
    game_running: bool
    game_paused: bool


class ResetResponse(BaseModel):
    """Reset operation response."""
    status: str
    action: str
    state: dict[str, Any]


class StepResponse(BaseModel):
    """Single step response."""
    status: str
    action: str
    state: dict[str, Any]
    result: dict[str, Any]


# ── WebSocket Endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/game")
async def websocket_game_endpoint(websocket: WebSocket) -> None:
    """
    Real-time WebSocket endpoint for game state streaming.

    Clients connect here to receive:
    - initial_state: First broadcast with current board position
    - move_complete: State updates after each agent move
    - critic_update: Additional critic analysis broadcast separately
    - reset: Game reset notification
    """
    await manager.connect(websocket)

    try:
        # Send initial state on connection
        state = load_game_state()
        await websocket.send_json({
            "type": "initial_state",
            "state": state
        })

        # Keep connection alive with ping/pong
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
        raise


# ── REST Control Endpoints ────────────────────────────────────────────────────

@app.post("/api/control")
async def api_control(command: ControlCommand) -> dict[str, Any]:
    """
    Handle user-driven game control actions.

    Supported commands:
    - start: Begin automated game loop
    - stop: Halt the game loop
    - pause: Toggle pause state
    - reset: Reset to starting position
    - step: Execute single move
    """
    try:
        if command.command == "reset":
            state = await orchestrator.reset_game()
            return {
                "status": "success",
                "action": "reset",
                "state": state
            }

        elif command.command == "start":
            await orchestrator.start()
            return {"status": "success", "action": "started"}

        elif command.command == "stop":
            await orchestrator.stop()
            return {"status": "success", "action": "stopped"}

        elif command.command == "pause":
            is_paused = orchestrator.pause_toggle()
            return {
                "status": "success",
                "action": "pause_toggled",
                "paused": is_paused
            }

        elif command.command == "step":
            result = await orchestrator.step_one_move()
            state = load_game_state()
            return {
                "status": "success",
                "action": "stepped",
                "state": state,
                "result": result
            }

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown command: {command.command}"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Configuration & Query Endpoints ───────────────────────────────────────────

@app.get("/api/settings", response_model=dict[str, Any])
async def get_settings() -> dict[str, Any]:
    """
    Reads and returns the agent profiles and configurations 
    from the root .claude/settings.json file.
    """
    settings_path = PROJECT_ROOT / ".claude" / "settings.json"
    
    if not settings_path.exists():
        return {}
        
    try:
        with open(settings_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading settings: {str(e)}")


@app.get("/api/game-state", response_model=dict[str, Any])
async def get_game_state() -> dict[str, Any]:
    """
    Get current game state (legacy - use WebSocket for real-time updates).

    Returns the latest JSON content from game_state/current.json.
    """
    try:
        return load_game_state()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Game state not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status", response_model=StatusResponse)
async def get_api_status() -> StatusResponse:
    """Health check endpoint."""
    return StatusResponse(
        status="healthy",
        websocket_clients=manager.get_connection_count(),
        game_running=orchestrator._running,
        game_paused=orchestrator._paused
    )


# ── Coach Agent Endpoints ─────────────────────────────────────────────────────

from app.agents.coach_agent import coach_agent

class CoachQuery(BaseModel):
    """Query model for /api/coach endpoint."""
    query: str | None = None
    fen: str | None = None


@app.post("/api/coach")
async def coach_query(query_data: CoachQuery) -> dict[str, Any]:
    """
    Handle coach chatbot queries using RAG pipeline.

    Accepts a natural language query and optional current FEN position.
    Returns a generated answer based on Mem0检索的lessons.

    Args:
        query_data: Contains 'query' (question) and optional 'fen' (position)

    Returns:
        Dictionary with 'answer', 'found_context', 'source_count'
    """
    try:
        result = await coach_agent.ask_coach(
            user_query=query_data.query or "",
            current_fen=query_data.fen
        )
        return result
    except Exception as e:
        return {
            "answer": f"I encountered an error processing your question: {str(e)}. Please try again.",
            "found_context": False,
            "source_count": 0
        }


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok", "message": "Chess Arena API is running"}


# ── Application Lifecycle ─────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event() -> None:
    """Always reset game to starting position on server startup."""
    init_game_state()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up on server shutdown."""
    if orchestrator._running:
        await orchestrator.stop()