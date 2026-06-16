---
paths:
  - scripts/black-player/choose_move.py
  - scripts/black-player/evaluate.py
---

# Black Player — Middlegame Rules (Moves 11–30)

## Evaluation Priority (score each candidate move)
```
+1000  Delivers checkmate
+500   Forced checkmate in 2
+90    Captures the enemy Queen (undefended or winning trade)
+50    Delivers check that wins material
+30    Captures Rook (if equal or better trade)
+15    Captures Bishop or Knight
+5     Captures Pawn
+10    Launches queenside pawn storm (b5, a5) when White castled kingside
+8     Delivers check (non-winning)
+7    Creates a passed pawn on queenside
+6     Controls e5/d5/e4/d4 (center)
+5     Opens the c-file or b-file for Rook (typical Sicilian plan)
-50    Hangs a piece undefended
-30    Allows opponent checkmate next move
-20    Allows capture of own Queen
```

## Black's Core Middlegame Plans

### If White castled Kingside → launch queenside attack
- Advance `b7b5`, `a7a5` — pawn storm on queenside
- Open the b-file or c-file for Black Rooks
- Trade off White's key defenders with piece exchanges

### If White castled Queenside → launch kingside attack
- Advance `g7g5`, `h7h5` — pawn storm on kingside
- Swing Rooks to the g- and h-files
- Sacrifice a pawn to crack open the White King's shelter

### If position is closed → maneuver for the better square
- Reroute Knights to outpost squares (e5, d4)
- Prepare a pawn break (`d5` or `f5`) to open the position

## Tactical Patterns Black Seeks
- **Counterattack**: When attacked, look for an even stronger counter-threat before defending
- **Exchange sacrifice**: Give a Rook for a Knight/Bishop to destroy White's pawn structure
- **Back-rank weakness**: White's back rank often weak after castling — probe with Rook or Queen
- **Zwischenzug (in-between move)**: Instead of recapturing, play a stronger intermediate move first

## When Behind in Material
- Seek complications — the sharper and more chaotic, the better
- Keep Queens on the board (easier to create mating threats)
- Offer pawn sacrifices to open files toward White's King