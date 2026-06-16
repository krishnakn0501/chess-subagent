---
paths:
  - scripts/white-player/choose_move.py
  - scripts/white-player/evaluate.py
---

# White Player — Middlegame Rules (Moves 11–30)

## Evaluation Priority (score each candidate move)
```
+1000  Delivers checkmate
+500   Delivers checkmate in 2 (forced sequence)
+90    Captures the enemy Queen (undefended or winning trade)
+50    Delivers check that wins material
+30    Captures Rook (if equal or better trade)
+15    Captures Bishop or Knight
+5     Captures Pawn
+8     Delivers check (non-winning)
+6     Controls e4/d4/e5/d5 (center square)
+4     Develops a previously unmoved piece
+3     Improves piece to a more active square
-50    Hangs (leaves) a piece undefended and capturable
-30    Allows opponent checkmate next move
-20    Allows capture of own Queen
-10    Allows capture of own Rook
```

## Tactical Patterns to Look For
- **Fork**: One piece attacks two enemy pieces simultaneously (Knights are best forkers)
- **Pin**: Attack a piece that cannot move without exposing a more valuable piece behind it
- **Skewer**: Attack a high-value piece that must move, exposing a lesser piece behind
- **Discovered attack**: Move one piece to unleash an attack from a piece behind it
- **Back-rank weakness**: If Black's back rank has no escape squares, Rook or Queen delivers checkmate

## Piece Activity Rules
- Rooks belong on open files (no pawns) or the 7th rank
- Knights are strongest on e5, d5, f5 — deep in enemy territory
- Bishops need open diagonals — if yours is blocked by your own pawns, restructure
- Queen is safest behind your own pawns, active only when opponent is weak

## When Ahead in Material
- Simplify: trade pieces but NOT pawns
- Push for a winning endgame — an extra Rook or Queen wins cleanly
- Avoid unnecessary complications that let Black back into the game