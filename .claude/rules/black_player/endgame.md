---
paths:
  - scripts/black-player/choose_move.py
  - scripts/black-player/evaluate.py
---

# Black Player — Endgame Rules

## Trigger: Switch to endgame logic when
- Both Queens have been traded off, OR
- Total pieces on board (excluding Kings and Pawns) ≤ 4

## When Equal or Ahead — Win It
- Activate the King immediately — march to center
- Identify your most advanced passed pawn and escort it
- Trade Rooks only if your pawn endgame is winning (count opposition)
- **Opposition**: place your King directly opposite White King with one square between — you control the approach

## When Behind — Save It (Drawing Techniques)
Black's primary goal when losing: force a draw.

### Stalemate Traps
- Sacrifice material to strip down to King only
- Maneuver King into a corner where White has no legal non-stalemate move
- Give up all pieces if it forces stalemate

### Fortress Defense
- Create a position where White cannot break through even with extra material
- E.g. Bishop + Rook pawn on wrong color = automatic draw if King reaches corner

### Perpetual Check
- If behind in material, look for a sequence where you can check forever
- Offer repeated checks — White must accept a draw or risk losing

### Philidor Position (Rook endgame defense)
- Place Rook on the 6th rank (cut off White King)
- When White's pawn advances to 6th, switch Rook to back rank for checking distance
- This holds the draw against Rook + Pawn vs Rook

## Pawn Endgame Rules
- **Key squares**: A pawn's key squares are 2 ranks ahead (e.g. e4 pawn → e6/d6/f6)
  - If Black King reaches a key square, the position is drawn regardless
- **Triangulation**: waste a move with the King to force opponent into zugzwang (losing move obligation)
- Count tempi carefully — one extra pawn move can decide the game