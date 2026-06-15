"""
stockfish_evaluator.py — Stockfish engine integration for position evaluation.

Provides:
- Position analysis using python-chess Stockfish engine wrapper
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
import chess.engine
from pathlib import Path
from typing import Optional, Any
import asyncio


class StockfishEvaluator:
    """
    Async Stockfish evaluator with win probability and PV line extraction.

    Features:
    - Analyzes positions to configurable depth
    - Converts centipawn/mate scores to win percentages
    - Extracts principal variation in UCI notation
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

    def __init__(self, stockfish_path: Optional[str] = None):
        """
        Initialize Stockfish evaluator.

        Args:
            stockfish_path: Path to Stockfish binary. Defaults to STOCKFISH_PATH env var
                           or "backend/bin/stockfish".
        """
        self.stockfish_path = stockfish_path or os.getenv(
            "STOCKFISH_PATH"
        )
        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._initialized = False

    async def initialize(self) -> bool:
        """
        Initialize Stockfish engine connection.

        Returns:
            True if initialization successful, False otherwise.
        """
        if self._initialized:
            return True

        try:
            # Check if Stockfish binary exists
            if not os.path.exists(self.stockfish_path):
                print(f"[Stockfish] Path not found: {self.stockfish_path}")
                return False

            # Initialize engine
            self._engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
            self._initialized = True
            print(f"[Stockfish] Engine initialized: {self.stockfish_path}")
            return True

        except Exception as e:
            print(f"[Stockfish] Initialization failed: {e}")
            return False

    async def _analyze_position_with_retry(self, board: chess.Board) -> Optional[chess.engine.PlayResult]:
        """
        Analyze a position with 3-retry logic and exponential backoff.

        Args:
            board: Chess board position to analyze.

        Returns:
            Analysis result or None if all retries fail.
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                if not self._initialized:
                    if not await self.initialize():
                        raise RuntimeError("Stockfish engine not initialized")

                # Use go depth command for controlled analysis
                info = self._engine.analyse(board, chess.engine.Limit(depth=self.DEPTH))
                return info

            except Exception as e:
                last_error = e
                wait_time = (2 ** attempt) * 0.5  # Exponential backoff: 0.5s, 1s, 2s

                if attempt < self.MAX_RETRIES - 1:
                    print(f"[Stockfish] Retry {attempt + 1}/{self.MAX_RETRIES} after {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)

        print(f"[Stockfish] All {self.MAX_RETRIES} retries failed: {last_error}")
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
            raw_score: The score dictionary from python-chess engine info.

        Returns:
            Tuple of (sanitized_cp_value, has_lowerbound, has_upperbound).
        """
        has_lowerbound = raw_score.get("lowerbound", False)
        has_upperbound = raw_score.get("upperbound", False)

        # Handle mate scores
        if "mate" in raw_score:
            mate_in = raw_score["mate"]
            is_white_mate = raw_score.get("is_white_mate", True)
            return 99999.0 if is_white_mate else -99999.0, has_lowerbound, has_upperbound

        # Handle centipawn scores
        if "cp" in raw_score:
            cp = raw_score["cp"]
            # Handle string values that might contain non-numeric characters
            try:
                return float(cp), has_lowerbound, has_upperbound
            except (ValueError, TypeError):
                return 0.0, has_lowerbound, has_upperbound

        # Default case
        return 0.0, has_lowerbound, has_upperbound

    def _extract_pv_line(self, info: dict) -> list[str]:
        """
        Extract Principal Variation and convert to UCI notation.

        Args:
            info: Engine info dictionary containing 'pv' field.

        Returns:
            List of UCI move strings (e.g., ["e2e4", "e7e5", "g1f3"]).
        """
        pv_moves = []

        if "pv" not in info:
            return pv_moves

        pv = info["pv"]

        # pv is a list of chess.Move objects
        for move in pv:
            uci_notation = move.uci()
            pv_moves.append(uci_notation)

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
            # Sanitize FEN before parsing
            fen = self.sanitize_fen(fen)

            # Parse FEN into chess.Board
            board = chess.Board(fen)

            # Analyze with retry logic
            info = await self._analyze_position_with_retry(board)

            if info is None:
                result["error"] = "Analysis failed after retries"
                return result

            # Extract score information
            if "score" in info:
                pov_score = info["score"]
                white_score = pov_score.white() # Cast score to White's perspective

                if white_score.is_mate():
                    # Handle Checkmate
                    result["is_mate"] = True
                    moves_to_mate = white_score.mate()
                    result["mate_in"] = abs(moves_to_mate)
                    
                    if moves_to_mate > 0:
                        result["white_prob"] = 100.0
                        result["black_prob"] = 0.0
                    else:
                        result["white_prob"] = 0.0
                        result["black_prob"] = 100.0
                        
                    result["raw_score"] = f"M{moves_to_mate}"
                    result["cp_value"] = 10000.0 if moves_to_mate > 0 else -10000.0

                else:
                    # Handle Centipawns safely (score() handles bounds implicitly)
                    cp_value = white_score.score()
                    
                    # Logistic Sigmoid Formula for win probability
                    white_decimal = 1.0 / (1.0 + 10.0 ** (-cp_value / 400.0))
                    
                    result["white_prob"] = round(white_decimal * 100, 1)
                    result["black_prob"] = round((1.0 - white_decimal) * 100, 1)
                    result["raw_score"] = f"cp {cp_value}"
                    result["cp_value"] = float(cp_value)
            else:
                result["error"] = "Engine did not return a score."
                return result
            # ---------------------------------------------------------

            # Extract PV line if requested
            if include_pv and "pv" in info:
                # Ensure the PV line is converted from Move objects to SAN/UCI strings
                # Depending on how _extract_pv_line is written, you might just need:
                # result["pv_line"] = [board.san(move) for move in info["pv"]]
                result["pv_line"] = self._extract_pv_line(info)

        except Exception as e:
            result["error"] = f"Failed to analyze position: {str(e)}"
            print(f"[Stockfish Evaluator] Error analyzing position: {e}")

        return result

    def close(self) -> None:
        """Close the Stockfish engine connection."""
        if self._engine:
            try:
                self._engine.quit()
                self._initialized = False
                print("[Stockfish] Engine closed")
            except Exception as e:
                print(f"[Stockfish] Error closing engine: {e}")

    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        self.close()
