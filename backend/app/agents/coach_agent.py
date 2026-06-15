"""
coach_agent.py — RAG-based Coach Agent for chess strategy queries.

Implements a question-answering system using Long-Term Memory (Mem0) with:
- Query rewriting for better semantic search
- Vector-based retrieval of relevant lessons
- LLM-based answer synthesis with context

Features:
- RAG (Retrieval-Augmented Generation) pipeline
- Query rewriting to improve retrieval quality
- Context-aware answer generation
- Graceful degradation when context is unavailable
"""

import os
import json
import urllib.request
import urllib.error
import asyncio
from typing import Optional

# Path resolution
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com") + "/v1/messages"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

EMBEDDINGS_API_URL = os.environ.get("EMBEDDINGS_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode") + "/v1/embeddings"
EMBEDDINGS_MODEL = os.environ.get("EMBEDDINGS_MODEL_NAME", "/text-embedding-v1")

MAX_RETRIES = 3
RETRY_DELAY_BASE = 0.5


class CoachAgent:
    """
    RAG-based Coach Agent for answering chess-related questions.
    """

    def __init__(self):
        """Initialize the Coach Agent."""
        self._initialized = False
        self._memory = None
        self._init_attempted = False

    def _initialize_memory(self) -> bool:
        """Initialize memory client if available."""
        if self._init_attempted:
            return self._memory is not None

        self._init_attempted = True
        try:
            from engine.memory_manager import get_qwen_memory_client
            self._memory = get_qwen_memory_client()
            if self._memory:
                self._initialized = True
                print("[Coach] Memory client initialized")
        except Exception as e:
            print(f"[Coach] Memory initialization failed: {e}")

        return self._memory is not None

    async def ask_coach(self, user_query: str, current_fen: Optional[str] = None) -> dict:
        """
        Answer a user query using RAG pipeline.

        Args:
            user_query: The user's natural language question
            current_fen: Optional current board position in FEN format

        Returns:
            Dictionary with:
            - answer: The generated response
            - found_context: Whether relevant memories were found
            - source_count: Number of memory sources used
        """
        # Initialize if needed
        if self._memory is None:
            self._initialize_memory()

        # Step 1: Rewrite query for better semantic search
        rewritten_query = await self._rewrite_query(user_query, current_fen)

        # Step 2: Semantic search in Mem0
        retrieved_memories = []
        if self._memory:
            retrieved_memories = await self._semantic_search(rewritten_query, current_fen)

        # Step 2b: Extract recent game context from Mem0
        game_contexts = await self._extract_game_context()

        # Step 3: Synthesize answer with LLM (dual-pipeline: prediction vs general)
        answer = await self._synthesize_answer(
            original_query=user_query,
            rewritten_query=rewritten_query,
            retrieved_memories=retrieved_memories,
            game_contexts=game_contexts,
            current_fen=current_fen
        )

        return {
            "answer": answer,
            "found_context": len(retrieved_memories) > 0,
            "source_count": len(retrieved_memories),
            "retrieved_queries": [m.get("query", "") for m in retrieved_memories[:3]] if retrieved_memories else []
        }

    async def _rewrite_query(self, user_query: str, current_fen: Optional[str] = None) -> str:
        """
        Rewrite user query into a dense, vector-friendly search string.

        Args:
            user_query: Original user query
            current_fen: Current board position (optional)

        Returns:
            Rewritten query optimized for semantic search
        """
        system_prompt = """You are a query rewriting assistant for a chess coaching system.
Your task: Convert the user's natural language question into a concise, vector-search-friendly query.
Focus on the core chess concepts, principles, or positions mentioned.

Rules:
- Keep the query Under 20 words
- Extract key chess terms and concepts
- Remove conversational filler words
- Preserve the intent and-specific chess context

Return ONLY the rewritten query, nothing else."""

        # Build context with current FEN if provided
        context = user_query
        if current_fen:
            # Extract opening section from FEN for context
            position = current_fen.split()[0][:30]
            context = f"Current position: {position}\n\nQuestion: {user_query}"

        payload = {
            "model": MODEL,
            "max_tokens": 100,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": context}
            ]
        }

        data = json.dumps(payload).encode("utf-8")

        for attempt in range(MAX_RETRIES):
            try:
                def make_request():
                    req = urllib.request.Request(
                        API_URL,
                        data=data,
                        headers={
                            "Content-Type": "application/json",
                            "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
                        },
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                        for block in body.get("content", []):
                            if block.get("type") == "text":
                                return block["text"].strip()
                        return None

                result = await asyncio.to_thread(make_request)
                if result:
                    return result
                return user_query  # Fallback to original on empty response

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
                    continue
                return user_query  # Fallback to original on final attempt

        return user_query

    async def _semantic_search(self, query: str, current_fen: Optional[str] = None) -> list:
        """
        Perform semantic search in Mem0.

        Args:
            query: Rewritten query string
            current_fen: Current board position (optional, for filtering)

        Returns:
            List of relevant memory entries
        """
        try:
            # Build search query
            search_query = query

            # Add FEN positional context if available
            if current_fen:
                position_attrs = current_fen.split()
                if len(position_attrs) >= 2:
                    turn = position_attrs[1]
                    search_query += f" position turn:{turn}"

            # SearchMem0
            results = self._memory.search(
                query=search_query,
                filters={"type": "critic_feedback"} if hasattr(self._memory, 'search') else None
            )

            # Handle different response formats
            if isinstance(results, dict) and "results" in results:
                results_list = results["results"]
            elif isinstance(results, list):
                results_list = results
            else:
                results_list = []

            # Extract memory text from results
            memories = []
            for r in results_list[:5]:  # Top 5 results
                if isinstance(r, dict):
                    memory_text = r.get("memory", "")
                    score = r.get("score", r.get("relevance_score", 0))
                    memories.append({"text": memory_text, "score": score})

            # Sort by relevance score
            memories.sort(key=lambda x: x.get("score", 0), reverse=True)

            return memories

        except Exception as e:
            print(f"[Coach] Semantic search failed: {e}")
            return []

    async def _synthesize_answer(self, original_query: str, rewritten_query: str,
                                 retrieved_memories: list, current_fen: Optional[str],
                                 game_contexts: list | None = None) -> str:
        """
        Synthesize answer using LLM with retrieved context.
        Dual-pipeline: detects prediction vs general chess queries.

        Args:
            original_query: Original user query
            rewritten_query: Rewritten query used for search
            retrieved_memories: List of retrieved memory entries
            current_fen: Current board position
            game_contexts: Recent game entries from Mem0 (optional)

        Returns:
            Generated answer string
        """
        system_prompt = """You are an expert chess coach named 'Chess Mentor' designed to help users understand chess strategies, learn from game analysis, and improve their gameplay.

Your capabilities:
- General chess knowledge: openings, tactics (forks, pins, skewers), strategy, endgames
- Current game analysis: predict outcomes from FEN positions, consider material balance and patterns
- Lesson recall: reference specific past positions from our stored game analysis memory
- Move history reasoning: reconstruct and analyze sequences of moves from memory entries

When answering:
1. Detect if question is GENERAL CHESS (openings, tactics, principles) vs CURRENT GAME (prediction, outcome)
2. For general questions: answer directly using chess knowledge
3. For current-game predictions: analyze the provided FEN, consider material balance and key factors, cite relevant lessons from memory
4. Cite specific lessons or principles when relevant
5. If no memories found AND question isn't about general chess, acknowledge honestly: "This isn't in my current training context"
6. Be concise (3-5 sentences for simple questions, up to 10 for complex ones)
7. Be encouraging and educational in tone
8. If the question is not about chess at all, politely say it's outside your domain"""

        # Build context: game contexts (recent moves) + retrieved memories
        game_context_text = ""
        if game_contexts:
            game_context_text = "\n".join([
                f"- [{c['color']}] {c['memory']}" for c in game_contexts[:5]
            ])

        memories_text = ""
        if retrieved_memories:
            memories_text = "\n\n".join([
                f"Memory {i+1}: {m.get('text', '')}"
                for i, m in enumerate(retrieved_memories[:3])
            ])

        # Dual-pipeline context
        if self._is_prediction_query(original_query):
            context = f"""ANALYZE THIS POSITION:
FEN: {current_fen if current_fen else 'Not provided'}

RECENT GAME PATTERNS FROM MEMORY:
{game_context_text if game_context_text else 'No recent game history found.'}

RETRIEVED LESSONS:
{memories_text if memories_text else 'No specific lessons found.'}

Based on the current position and historical patterns, provide your prediction and reasoning."""
        else:
            context = f"""USER QUESTION: {original_query}

RETRIEVED LESSONS (reference if relevant):
{memories_text if memories_text else 'No specific lessons found in memory.'}

RECENT GAME CONTEXT:
{game_context_text if game_context_text else 'No recent game history found.'}

Base your answer on these lessons and game context when they help answer the question. If the question is about general chess, provide a direct answer using your knowledge."""

        # Add current position context if provided (separate from prediction)
        if current_fen and not self._is_prediction_query(original_query):
            context += f"""

CURRENT POSITION (if relevant to your question):
{current_fen}

If your question is about this specific position, analyze it in your answer."""

        # User prompt
        user_prompt = f"""QUESTION: {original_query}

Answer the question clearly and helpfully. If the question is about a specific position and no relevant memories were found, you may ask for more details or provide general advice.

Your answer:"""

        payload = {
            "model": MODEL,
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": f"{context}\n\n{user_prompt}"}
            ]
        }

        data = json.dumps(payload).encode("utf-8")

        for attempt in range(MAX_RETRIES):
            try:
                def make_request():
                    req = urllib.request.Request(
                        API_URL,
                        data=data,
                        headers={
                            "Content-Type": "application/json",
                            "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
                        },
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                        for block in body.get("content", []):
                            if block.get("type") == "text":
                                answer = block["text"].strip()
                                # Clean up the answer
                                answer = answer.replace("Answer:", "").strip()
                                return answer
                        return None

                result = await asyncio.to_thread(make_request)
                if result:
                    return result
                return "I couldn't generate a proper answer. Please try rephrasing your question."

            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
                    continue
                return f"I encountered an error while generating an answer: {str(e)}. Please try again."

        return "I'm having trouble connecting to my knowledge base. Please try again later."

    # Prediction detection helpers
    _PREDICTION_KEYWORDS = [
        "predict", "who will win", "likely outcome", "forecast",
        "will white", "will black", "game ending", "result", "score",
        "prospects", "favour", "advantage"
    ]

    def _is_prediction_query(self, query: str) -> bool:
        """Detect if the query relates to predicting the current game outcome."""
        return any(kw in query.lower() for kw in self._PREDICTION_KEYWORDS)

    async def _extract_game_context(self) -> list[dict]:
        """Extract recent lesson entries from Mem0 for both players.
        Returns list of dicts with color and memory text."""
        contexts = []
        if not self._memory:
            return contexts

        for color in ["white_player_v1", "black_player_v1"]:
            try:
                results = self._memory.search(
                    query="recent chess moves analysis critic feedback",
                    filters={"user_id": color}
                )
                if isinstance(results, dict) and "results" in results:
                    results_list = results["results"]
                elif isinstance(results, list):
                    results_list = results
                else:
                    results_list = []

                for r in results_list[:3]:
                    if isinstance(r, dict):
                        mem_text = r.get("memory", "")
                        if mem_text:
                            contexts.append({"color": color, "memory": mem_text})
            except Exception as e:
                print(f"[Coach] Failed to extract context for {color}: {e}")

        return contexts

    async def get_critic_lessons(self, color: str) -> list:
        """
        Get all critic lessons for a specific player color.

        Args:
            color: "white" or "black"

        Returns:
            List of lessons for the specified player
        """
        try:
            if not self._memory:
                return []

            results = self._memory.search(
                query="chess lessons critic feedback",
                filters={"user_id": f"{color}_player_v1"}
            )

            if isinstance(results, dict) and "results" in results:
                results_list = results["results"]
            elif isinstance(results, list):
                results_list = results
            else:
                results_list = []

            return [r.get("memory", "") for r in results_list if isinstance(r, dict)]

        except Exception as e:
            print(f"[Coach] Failed to retrieve lessons: {e}")
            return []


# Global instance
coach_agent = CoachAgent()
