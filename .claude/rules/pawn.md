---
description: This file describes the movement rules for the Pawn piece in chess.
paths:
  - src/pieces/pawn.py
  - scripts/validate_move.py
  - scripts/apply_move.py
---

# Pawn Rules

## Movement
- Moves **forward only** (White: up the board / decreasing row index; Black: down / increasing row index)
- Advances **one square** forward if the target square is empty
- Advances **two squares** forward from its starting rank only (rank 2 for White, rank 7 for Black)
  - Both the target square AND the intermediate square must be empty
- Cannot move backward or sideways

## Captures
- Captures **diagonally forward** one square (one file left or right, one rank forward)
- Cannot capture directly forward

## En Passant
- When an enemy pawn advances two squares in a single move past your pawn's attack square:
  - Your pawn MAY capture it as if it had only moved one square
  - This capture is ONLY legal on the very next move — it cannot be saved for later
  - The captured pawn is removed from the square it occupies (not the destination square)
- In game state: `en_passant` field stores the target square (e.g. `"e6"`) if en passant is available

## Promotion
- When a pawn reaches the opposite back rank (rank 8 for White, rank 1 for Black):
  - It MUST be promoted — it cannot remain a pawn
  - Replace it with a Queen, Rook, Bishop, or Knight of the same color
  - Default: always promote to Queen unless there is a specific tactical reason
- Move notation: `e7e8Q` (pawn on e7 moves to e8 and promotes to Queen)

## Notation
- In board state: `P` (White pawn), `p` (Black pawn)
- Pawn moves in scripts use origin+destination: `e2e4`, `d7d5`
- Captures same format: `e4d5` (pawn on e4 captures on d5)

## Value
- Material value: **1 point**
- Connected passed pawns, especially in endgame, are worth significantly more