"""
stockfish_evaluator.py — Stockfish engine integration for position evaluation via HTTP.

Provides:
- Position analysis using serverless Stockfish microservice
- Win probability calculation from centipawn/mate scores
- Principal Variation (PV) line extraction in UCI notation
- Robust error handling with 3-retry logic

Usage:
    from engine.stockfish_evaluator import StockfishEvaluator

    evaluator = StockfishEvaluator()
    result = await evaluator.get_win_probability(fen_string)
"""

import os
import chess
import httpx
from pathlib import Path
from typing import Optional, Any
import asyncio


class StockfishEvaluator:
    """
    Async Stockfish evaluator via HTTP with win probability and PV line extraction.

    Features:
    - Analyzes positions to configurable depth via remote serverless endpoint
    - Converts centipawn/mate scores to win percentages
    - Extracts principal variation in UCI notation (simulated/derived from response if needed)
    - Handles mate scores and bound flags robustly
    - Implements 3-retry logic with exponential backoff
    """

    MAX_RETRIES = 3
    DEPTH = 15  # Analysis depth

    @staticmethod
    def sanitize_fen(fen: str) -> str:
        """
        Sanitize FEN string to ensure compatibility with Stockfish.

        Fixes common issues:
        - Converts 'white'/'black' to 'w'/'b'
        - Ensures all 6 FEN fields are present
        """
        parts = fen.split()
        if len(parts) > 1:
            turn = parts[1].lower()
            if turn in ("white", "w"):
                parts[1] = "w"
            elif turn in ("black", "b"):
                parts[1] = "b"
        # Ensure minimum FEN fields (position, turn, castling, ep, halfmove, fullmove)
        while len(parts) < 6:
            parts.append("0" if len(parts) >= 4 else "-")
        return " ".join(parts)

    def __init__(self, stockfish_url: Optional[str] = None):
        """
        Initialize Stockfish evaluator.

        Args:
            stockfish_url: URL to the serverless Stockfish endpoint. Defaults to ENGINE_URL env var
                           or "http://localhost:3002/api/evaluate" for local dev.
        """
        base_url = stockfish_url or os.getenv("ENGINE_URL", "http://localhost:3002")
        base_url = base_url.rstrip('/')
        self.stockfish_url = f"{base_url}/api/evaluate"
        self._initialized = True

    async def initialize(self) -> bool:
        """
        Initialize Stockfish evaluator (no-op for HTTP version).

        Returns:
            True (always, as it's a stateless HTTP client).
        """
        return self._initialized

    async def _analyze_position_with_retry(self, fen: str) -> Optional[dict[str, Any]]:
        """
        Analyze a position with 3-retry logic and exponential backoff via HTTP.

        Args:
            fen: FEN string to analyze.

        Returns:
            Analysis result dictionary or None if all retries fail.
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        self.stockfish_url,
                        json={"fen": fen, "depth": self.DEPTH}
                    )
                    response.raise_for_status()
                    return response.json()

            except Exception as e:
                last_error = e
                wait_time = (2 ** attempt) * 0.5  # Exponential backoff: 0.5s, 1s, 2s

                if attempt < self.MAX_RETRIES - 1:
                    print(f"[Stockfish] HTTP Retry {attempt + 1}/{self.MAX_RETRIES} after {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)

        print(f"[Stockfish] All {self.MAX_RETRIES} HTTP retries failed: {last_error}")
        return None

    def _calculate_win_probability(self, cp_score: float) -> tuple[float, float]:
        """
        Calculate win probabilities from centipawn score using logistic sigmoid.

        Formula: P(White) = 1 / (1 + 10^(-score/400))

        Args:
            cp_score: Centipawn score (positive = White advantage).

        Returns:
            Tuple of (white_win_percent, black_win_percent).
        """
        import math

        # Convert centipawns to score ratio
        score_ratio = cp_score / 400.0
        white_prob = 1.0 / (1.0 + 10 ** (-score_ratio))
        black_prob = 1.0 - white_prob

        return round(white_prob * 100, 2), round(black_prob * 100, 2)

    def _handle_mate_score(self, is_white_mate: bool, mate_in: int) -> tuple[float, float]:
        """
        Handle forced mate scores.

        Args:
            is_white_mate: True if mate is for White, False for Black.
            mate_in: Number of moves to mate.

        Returns:
            Tuple of (white_win_percent, black_win_percent).
        """
        if is_white_mate:
            # Near-certain win for White
            return 100.0, 0.0
        else:
            # Near-certain loss for White
            return 0.0, 100.0

    def _sanitize_cp_value(self, raw_score: dict) -> tuple[float, bool, bool]:
        """
        Safely extract centipawn value handling bounds and edge cases.

        Args:
            raw_score: The score dictionary from HTTP response (contains 'cp' or implies mate).

        Returns:
            Tuple of (sanitized_cp_value, has_lowerbound, has_upperbound).
        """
        # For HTTP, we just get a flat cp value. We'll simulate bounds if needed, but usually not present.
        has_lowerbound = False
        has_upperbound = False

        cp = raw_score.get("cp")
        if cp is not None:
            try:
                return float(cp), has_lowerbound, has_upperbound
            except (ValueError, TypeError):
                return 0.0, has_lowerbound, has_upperbound

        return 0.0, has_lowerbound, has_upperbound

    def _extract_pv_line(self, info: dict) -> list[str]:
        """
        Extract Principal Variation.
        Note: The simple serverless endpoint currently returns best_move and cp.
        To get full PV, we'd need to enhance the Node.js endpoint. For now, returning [best_move] if available.
        """
        pv_moves = []
        if "best_move" in info:
            pv_moves.append(info["best_move"])
        return pv_moves

    async def get_win_probability(
        self,
        fen: str,
        include_pv: bool = True
    ) -> dict[str, Any]:
        """
        Get win probabilities for a position with optional PV line.

        Args:
            fen: FEN string of the position to analyze.
            include_pv: Whether to extract and return the PV line.

        Returns:
            Dictionary with format:
            {
                "white_prob": 55.5,      # White win percentage
                "black_prob": 44.5,      # Black win percentage
                "raw_score": "cp 15",    # Original score representation
                "cp_value": 15.0,        # Sanitized centipawn value
                "is_mate": False,        # Whether this is a mate score
                "mate_in": None,         # Moves to mate (if applicable)
                "pv_line": ["e2e4", ...], # Principal variation (if requested)
                "error": None            # Error message if analysis failed
            }
        """
        result = {
            "white_prob": 50.0,
            "black_prob": 50.0,
            "raw_score": "unknown",
            "cp_value": 0.0,
            "is_mate": False,
            "mate_in": None,
            "pv_line": [],
            "error": None
        }

        try:
            # Sanitize FEN before sending
            fen = self.sanitize_fen(fen)

            # Analyze with retry logic
            info = await self._analyze_position_with_retry(fen)

            if info is None:
                result["error"] = "Analysis failed after retries"
                return result

            if "error" in info:
                result["error"] = info["error"]
                return result

            cp_value = info.get("cp", 0)
            best_move = info.get("best_move", "")

            # Check for mate heuristic (cp >= 9000 or <= -9000)
            if abs(cp_value) >= 9000:
                result["is_mate"] = True
                result["mate_in"] = 1 # Simplified for HTTP response
                if cp_value > 0:
                    result["white_prob"] = 100.0
                    result["black_prob"] = 0.0
                else:
                    result["white_prob"] = 0.0
                    result["black_prob"] = 100.0
                result["raw_score"] = f"M{1}"
                result["cp_value"] = float(cp_value)
            else:
                # Logistic Sigmoid Formula for win probability
                white_decimal = 1.0 / (1.0 + 10.0 ** (-cp_value / 400.0))

                result["white_prob"] = round(white_decimal * 100, 1)
                result["black_prob"] = round((1.0 - white_decimal) * 100, 1)
                result["raw_score"] = f"cp {cp_value}"
                result["cp_value"] = float(cp_value)

            # Extract PV line if requested
            if include_pv:
                result["pv_line"] = self._extract_pv_line(info)

        except Exception as e:
            result["error"] = f"Failed to analyze position: {str(e)}"
            print(f"[Stockfish Evaluator] Error analyzing position: {e}")

        return result

    def close(self) -> None:
        """Close the Stockfish engine connection (no-op for HTTP)."""
        pass

    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        pass