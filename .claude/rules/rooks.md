---
description: This file describes the movement rules for the Rook piece in chess.
paths:
  - src/pieces/rook.py
  - scripts/validate_move.py
  - scripts/apply_move.py
---
# Rook Rules

## Movement
- Moves any number of vacant squares horizontally along ranks or vertically along files.
- Cannot jump over other pieces.
- Captures by occupying the square of an enemy piece.

## Notation
- In board.py / game state: R (White Rook), r (Black Rook)
- In PGN: R (e.g., Ra1, Rxd8)

## Critical Constraints
- Once a Rook moves, it permanently loses the ability to participate in Castling for the remainder of the game, even if it returns to its starting square.
- Cannot move through squares occupied by friendly pieces.