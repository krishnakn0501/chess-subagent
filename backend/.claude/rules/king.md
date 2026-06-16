---
paths:
  - src/pieces/king.py
  - scripts/validate_move.py
  - scripts/apply_move.py
  
description: This file describes the movement rules for the King piece in chess.
---

# King Rules

## Movement
- Moves exactly **one square** in any direction (horizontal, vertical, diagonal)
- Cannot move to a square occupied by a friendly piece
- Cannot move to a square that is attacked by any enemy piece (would put itself in check)

## Castling
Two types — both require these conditions to ALL be true:

**Kingside (O-O):** King moves e1→g1 (White) or e8→g8 (Black)
- King has never moved this game
- Kingside Rook (h-file) has never moved
- Squares f1, g1 (or f8, g8) are empty
- King is not currently in check
- King does not pass through f1/f8 while in check
- King does not land on g1/g8 while in check

**Queenside (O-O-O):** King moves e1→c1 (White) or e8→c8 (Black)
- King has never moved this game
- Queenside Rook (a-file) has never moved
- Squares b1, c1, d1 (or b8, c8, d8) are empty
- King is not currently in check
- King does not pass through d1/d8 or c1/c8 while in check

## Notation
- In board.py / game state: `K` (White King), `k` (Black King)
- In scripts: castling represented as King moving 2 squares (e1g1 = kingside, e1c1 = queenside)
- In PGN: `O-O` (kingside), `O-O-O` (queenside)

## Critical Constraints
- The King is NEVER captured — check detection ends the attack line
- If in check, the active player MUST resolve check on their turn
- King cannot move adjacent to the enemy King (both would be in check simultaneously)