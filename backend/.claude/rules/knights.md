---
description: This file describes the movement rules for the Knight piece in chess.
paths:
  - src/pieces/knight.py
  - scripts/validate_move.py
  - scripts/apply_move.py
---
# Knight Rules

##  Movement
- Moves in an "L-shape": two squares in any orthogonal direction (horizontal or vertical), followed by one square in    perpendicular direction.
- The only piece that can leap over other pieces (both friendly and enemy) along its path.
- Captures by occupying the destination square of an enemy piece, not the pieces it leaps over.

## Notation
- In board.py / game state: N (White Knight), n (Black Knight)
- In PGN: N (e.g., Nf3, Ndxe4)

## Critical Constraints
- Because it leaps, a Knight's attack cannot be blocked by interposing a piece. If a King is placed in check by a Knight, the King must move or the Knight must be captured.