---
description: This file describes the movement rules for the Queen piece in chess.
paths:
- src/pieces/queen.py
- scripts/validate_move.py
- scripts/apply_move.py

---

# Queen Rules

## Movement
- Moves any number of vacant squares horizontally, vertically, or diagonally.
- Combines the power of a Rook and a Bishop.
- Cannot jump over other pieces (friendly or enemy).
- Captures by occupying the square of an enemy piece.

## Notation
- In board.py / game state: Q (White Queen), q (Black Queen)
- In PGN: Q (e.g., Qd4, Qxe5)

## Critical Constraints
- Cannot move through squares occupied by friendly pieces.
- If pinned to its own King, its movement is restricted to the line of the pin.