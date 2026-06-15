"""
memory_manager.py — Long-term memory management for chess agents.

Provides:
- Mem0-based semantic memory via Qwen embeddings (primary)
- JSON file fallback storage (secondary, when mem0 API fails)
- Store/retrieve lessons from critic feedback
- Robust error handling with graceful degradation

Storage locations:
- Primary: Local ChromaDB (via mem0)
- Fallback: backend/data/fallback_lessons.json

Usage:
    from engine.memory_manager import store_lesson, retrieve_relevant_lessons
    store_lesson("white", fen_string, lesson_text)
    lessons = retrieve_relevant_lessons("white", current_fen)
"""

import os
import json
from pathlib import Path
from typing import Any

# Fallback storage path
FALLBACK_STORAGE_PATH = Path(__file__).parent.parent.parent / "backend" / "data" / "fallback_lessons.json"

# Try to import mem0, fall back gracefully if unavailable
try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    print("[Memory Manager] mem0 not installed — using JSON fallback only")


def get_qwen_memory_client():
    """
    Initializes a hybrid Mem0 instance:
    - LLM: Qwen (via DashScope OpenAI-compatible endpoint)
    - Embedder: Qwen (via DashScope)
    - Storage: Local ChromaDB

    Returns None if mem0 is not available or configuration fails.
    """
    if not MEM0_AVAILABLE:
        return None

    # 1. Fetch the Qwen API Key
    qwen_api_key = os.getenv("MEM0_QWEN_API_KEY")
    if not qwen_api_key:
        print("⚠️ Warning: MEM0_QWEN_API_KEY environment variable is not set!")

    qwen_api_url = os.getenv("MEM0_QWEN_API_URL")
    if not qwen_api_url:
        print("⚠️ Warning: MEM0_QWEN_API_URL environment variable is not set!")

    qwen_model_name = os.getenv("MEM0_QWEN_MODEL_NAME")
    if not qwen_model_name:
        print("⚠️ Warning: MEM0_QWEN_MODEL_NAME environment variable is not set!")

    embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME")
    if not embeddings_model_name:
        print("⚠️ Warning: EMBEDDINGS_MODEL_NAME environment variable is not set!")

    # Embeddings base URL — must be OpenAI-compatible (/v1/embeddings endpoint).
    # DashScope's Anthropic proxy does NOT serve /v1/embeddings, so we use
    # the dedicated OpenAI-compatible endpoint instead.
    embeddings_base_url = os.getenv(
        "EMBEDDINGS_BASE_URL",
        "https://dashscope-intl.aliyuncs.com/compatible-mode"
    )


    embeddings_api_key = os.getenv("EMBEDDINGS_API_KEY")
    if not embeddings_api_key:
        print("⚠️ Warning: EMBEDDINGS_API_KEY environment variable is not set!")

    config = {
        # --- LOCAL STORAGE ---
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "chess_multi_agent_experiences",
                "path": "backend/data/mem0_storage"
            }
        },

        # --- QWEN EMBEDDER ---
        "embedder": {
            "provider": "openai",
            "config": {
                "api_key": embeddings_api_key,
                "openai_base_url": embeddings_base_url,
                "model": embeddings_model_name
            }
        },

        # --- QWEN LLM ---
        "llm": {
            "provider": "openai",
            "config": {
                "api_key": qwen_api_key,
                "openai_base_url": qwen_api_url,
                "model": qwen_model_name,
                "temperature": 0.7
            }
        }
    }

    try:
        return Memory.from_config(config)
    except Exception as e:
        print(f"[Memory Manager] Failed to initialize mem0: {e}")

        return None


# Global memory instance (may be None if mem0 unavailable)
memory = get_qwen_memory_client()


# ==========================================
# JSON Fallback Storage
# ==========================================

def _load_fallback_store() -> dict[str, list]:
    """Load the fallback JSON storage file. Returns empty dict if not found."""
    try:
        if FALLBACK_STORAGE_PATH.exists():
            with open(FALLBACK_STORAGE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Memory Manager] Error reading fallback storage: {e}")
    return {"white_player_v1": [], "black_player_v1": []}


def _save_fallback_store(data: dict[str, list]) -> None:
    """Save data to the fallback JSON storage file."""
    try:
        FALLBACK_STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(FALLBACK_STORAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"[Memory Manager] Error writing fallback storage: {e}")


def _store_lesson_fallback(player_color: str, fen_state: str, critic_lesson: str) -> None:
    """Store a lesson in the JSON fallback file."""
    store = _load_fallback_store()
    user_id = f"{player_color}_player_v1"

    if user_id not in store:
        store[user_id] = []

    store[user_id].append({
        "fen": fen_state,
        "lesson": critic_lesson,
        "timestamp": __import__("datetime").datetime.now().isoformat()
    })

    _save_fallback_store(store)
    print(f"[Memory Manager] Lesson stored in fallback JSON for {user_id}")


def _retrieve_lessons_fallback(player_color: str, current_fen: str) -> str:
    """
    Retrieve lessons from JSON fallback storage.
    Simple keyword matching on FEN structure since no embeddings available.
    """
    store = _load_fallback_store()
    user_id = f"{player_color}_player_v1"

    if user_id not in store or not store[user_id]:
        return "No relevant past experiences found for this position."

    lessons = store[user_id]

    # Extract FEN position (first field) for matching
    current_position = current_fen.split()[0] if current_fen else ""

    # Simple relevance: match lessons from similar opening structures
    # (first 15 chars of FEN position = piece arrangement)
    relevant = []
    for entry in lessons[-20:]:  # Check last 20 entries
        stored_fen = entry.get("fen", "")
        stored_position = stored_fen.split()[0] if stored_fen else ""

        # Match if first 15 chars of position overlap significantly
        if current_position[:15] == stored_position[:15]:
            relevant.append(entry["lesson"])
        elif current_position[:10] == stored_position[:10]:
            relevant.append(entry["lesson"])

    if not relevant:
        # If no positional match, return most recent lessons
        relevant = [entry["lesson"] for entry in lessons[-5:]]

    if not relevant:
        return "No relevant past experiences found for this position."

    formatted = "\n".join([f"- {lesson}" for lesson in relevant[:5]])
    return formatted


# ==========================================
# Public API — Unified Store/Retrieve
# ==========================================

def store_lesson(player_color: str, fen_state: str, critic_lesson: str) -> None:
    """
    Save a lesson to long-term memory.

    Tries mem0 first (semantic storage), falls back to JSON file on failure.

    Args:
        player_color: "white" or "black"
        fen_state: FEN string of the position
        critic_lesson: Lesson text from critic agent
    """
    # Try mem0 first
    if memory is not None:
        try:
            memory_text = f"In position {fen_state}, the following lesson was learned: {critic_lesson}"
            memory.add(
                memory_text,
                user_id=f"{player_color}_player_v1",
                metadata={"type": "critic_feedback"}
            )
            print(f"[Memory Manager] Lesson stored in mem0 for {player_color}_player_v1")
            # Also store in fallback for redundancy
            _store_lesson_fallback(player_color, fen_state, critic_lesson)
            return
        except Exception as e:
            print(f"[Memory Manager] mem0 store failed: {e} — using fallback")

    # Fallback to JSON
    _store_lesson_fallback(player_color, fen_state, critic_lesson)


def retrieve_relevant_lessons(player_color: str, current_fen: str) -> str:
    """
    Find past lessons related to the current board position.

    Tries mem0 semantic search first, falls back to JSON keyword matching.

    Args:
        player_color: "white" or "black"
        current_fen: Current FEN string

    Returns:
        Formatted string of relevant lessons
    """
    # Try mem0 first
    if memory is not None:
        try:
            fen_substring = current_fen.split()[0][:25]
            results = memory.search(
                query=f"Mistakes or strategic lessons regarding board structure {fen_substring}",
                filters={"user_id": f"{player_color}_player_v1"}
            )

            # --- THE FIX: Handle Mem0 v1.0+ Dictionary Response ---
            # Extract the actual list of memory objects depending on the API version
            if isinstance(results, dict) and "results" in results:
                results_list = results["results"]
            elif isinstance(results, list):
                results_list = results
            else:
                results_list = []

            # Safely iterate over the extracted list
            if results_list:
                # Use .get() to safely pull the string without crashing if the key is missing
                formatted_lessons = "\n".join([f"- {r.get('memory', '')}" for r in results_list if isinstance(r, dict)])
                return formatted_lessons
            # ------------------------------------------------------

        except Exception as e:
            print(f"[Memory Manager] mem0 search failed: {e} — using fallback")

    # Fallback to JSON storage
    return _retrieve_lessons_fallback(player_color, current_fen)