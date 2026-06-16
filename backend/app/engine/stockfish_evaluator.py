"""
stockfish_evaluator.py — Stockfish engine integration for position evaluation via local binary.

Provides:
- Position analysis using local Stockfish binary installed via Nixpacks
- Win probability calculation from centipawn/mate scores
- Principal Variation (PV) line extraction in UCI notation
- Direct Python interface to Stockfish engine

Usage:
    from engine.stockfish_evaluator import StockfishEvaluator

    evaluator = StockfishEvaluator()
    result = evaluator.get_win_probability(fen_string)  # Note: now synchronous
"""

import os
import chess
from pathlib import Path
from typing import Optional, Any
import shutil
from stockfish import Stockfish


class StockfishEvaluator:
    """
    Local Stockfish evaluator using the Python wrapper with win probability and PV line extraction.

    Features:
    - Analyzes positions to configurable depth via local Stockfish binary
    - Converts centipawn/mate scores to win percentages
    - Extracts principal variation in UCI notation from Stockfish analysis
    - Handles mate scores robustly
    - Direct local communication (no network calls)
    """

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
        Initialize Stockfish evaluator with local binary.

        Args:
            stockfish_path: Path to the Stockfish binary. Defaults to STOCKFISH_BINARY_PATH env var,
                            or dynamically searches for the system-installed binary.
        """
        # 1. Check for an explicit environment variable first
        env_path = os.getenv("STOCKFISH_BINARY_PATH")
        
        # 2. Actively hunt down the absolute path of the binary in the Linux container
        system_path = (
            shutil.which("stockfish") or 
            shutil.which("/usr/games/stockfish") or 
            shutil.which("/usr/bin/stockfish")
        )
        
        # 3. Determine the final path to use
        binary_path = stockfish_path or env_path or system_path
        
        if not binary_path:
            print("[Orchestrator] ❌ FATAL: Could not locate 'stockfish' binary in system paths.")
            self.engine = None
            self._initialized = False
            return

        try:
            self.engine = Stockfish(path=binary_path, depth=self.DEPTH)
            self._initialized = True
            print(f"[Orchestrator] Stockfish initialized successfully at {binary_path}! ✓")
        except Exception as e:
            print(f"[Orchestrator] ❌ FATAL: Failed to initialize Stockfish: {e}")
            self.engine = None
            self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize Stockfish evaluator (sync for local engine).

        Returns:
            True if initialization successful.
        """
        try:
            # Test the engine with a simple command
            self.engine.get_best_move()
            return True
        except Exception as e:
            print(f"[Stockfish] Initialization failed: {e}")
            return False

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

    def _extract_pv_line(self) -> list[str]:
        """
        Extract Principal Variation from the current Stockfish analysis.

        Returns:
            List of moves in the principal variation.
        """
        try:
            # Get the info from the last evaluation
            info = self.engine.info
            if "pv" in info:
                pv_moves = info["pv"].split()
                return pv_moves
            else:
                return []
        except:
            return []

    def get_win_probability(
        self,
        fen: str,
        include_pv: bool = True
    ) -> dict[str, Any]:
        """
        Get win probabilities for a position with optional PV line using local Stockfish.

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
            # Sanitize FEN before setting
            fen = self.sanitize_fen(fen)

            # Set the position in the local Stockfish engine
            self.engine.set_fen_position(fen)

            # Get the evaluation from Stockfish
            evaluation = self.engine.get_evaluation()

            # Extract the score type and value
            if evaluation['type'] == 'cp':  # centipawn
                cp_value = evaluation['value']

                # Check for mate heuristic (high cp values may indicate near-mate situations)
                if abs(cp_value) >= 10000:  # Very high value indicates mate
                    result["is_mate"] = True
                    # Determine if it's mate for white or black based on sign
                    if cp_value > 0:
                        # Mate for white
                        result["white_prob"] = 100.0
                        result["black_prob"] = 0.0
                        result["mate_in"] = abs(cp_value)  # This is a convention for mate in N
                    else:
                        # Mate for black
                        result["white_prob"] = 0.0
                        result["black_prob"] = 100.0
                        result["mate_in"] = abs(cp_value)  # This is a convention for mate in N
                    result["raw_score"] = f"#{'+' if cp_value > 0 else '-'}{abs(cp_value)}"
                    result["cp_value"] = float(cp_value)
                else:
                    # Calculate win probabilities from centipawn score
                    white_prob, black_prob = self._calculate_win_probability(cp_value)

                    result["white_prob"] = white_prob
                    result["black_prob"] = black_prob
                    result["raw_score"] = f"cp {cp_value}"
                    result["cp_value"] = float(cp_value)

            elif evaluation['type'] == 'mate':  # mate in N
                result["is_mate"] = True
                mate_in = evaluation['value']

                # Determine if mate is for white or black based on the sign
                if mate_in > 0:
                    # Mate for white
                    result["white_prob"] = 100.0
                    result["black_prob"] = 0.0
                else:
                    # Mate for black
                    result["white_prob"] = 0.0
                    result["black_prob"] = 100.0

                result["mate_in"] = abs(mate_in)
                result["raw_score"] = f"#{'+' if mate_in > 0 else '-'}{abs(mate_in)}"
                result["cp_value"] = float(mate_in * 10000)  # Represent mate as large centipawn value

            # Extract PV line if requested
            if include_pv:
                result["pv_line"] = self.engine.get_top_moves(5)  # Get top 5 moves as PV
                # Extract just the move strings from the top moves
                if isinstance(result["pv_line"], list) and len(result["pv_line"]) > 0:
                    if isinstance(result["pv_line"][0], dict):
                        result["pv_line"] = [move["Move"] for move in result["pv_line"]]
                    else:
                        result["pv_line"] = [str(move) for move in result["pv_line"]]

        except Exception as e:
            result["error"] = f"Failed to analyze position: {str(e)}"
            print(f"[Stockfish Evaluator] Error analyzing position: {e}")

        return result

    def close(self) -> None:
        """Close the Stockfish engine connection."""
        try:
            self.engine.quit()
        except:
            pass

    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        self.close()