---
description: This file describes the movement rules for the Bishop piece in chess.
applyTo: src/pieces/bishop.py, scripts/validate_move.py, scripts/apply_move.py
paths:
  - src/pieces/bishop.py
  -  scripts/validate_move.py
---

## Bishop Rules

### Movement
- Moves any number of vacant squares diagonally.
- Cannot jump over other pieces.
- Captures by occupying the square of an enemy piece.
  
### Notation
- In board.py / game state: B (White Bishop), b (Black Bishop)
- In PGN: B (e.g., Bc4, Bxf7)

### Critical Constraints
- A Bishop is strictly "color-bound," meaning it will remain on either the light squares or dark squares for the entire game.
- Cannot move through squares occupied by friendly pieces.