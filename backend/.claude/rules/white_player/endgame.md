---
paths:
  - scripts/white-player/choose_move.py
  - scripts/white-player/evaluate.py
---

# White Player — Endgame Rules (Few pieces remain)

## Trigger: Switch to endgame logic when
- Both Queens have been traded off, OR
- Total pieces on board (excluding Kings and Pawns) ≤ 4

## King Activation
- In the endgame, activate the King — it becomes a fighting piece
- March the King toward the center (e4, d4, e5, d5)
- Use the King to escort passed pawns to promotion

## Pawn Promotion Push
- A passed pawn (no enemy pawns blocking or flanking it) is a winning asset
- Calculate if your pawn can promote before the enemy King catches it:
  - **Rule of the Square**: draw a diagonal square from the pawn to the promotion rank — if enemy King is outside this square, it cannot stop promotion
- Always push the most advanced passed pawn first

## Rook Endgame Rules (most common endgame)
- Rook belongs **behind** your passed pawn (pushes it forward)
- Enemy Rook should be cut off on a rank or file away from your King/pawn
- Lucena Position (Rook + Pawn vs Rook) = winning technique — build a bridge
- Philidor Position (Rook vs Rook + Pawn) = drawing technique for the defender

## Winning with Extra Material
| Advantage | Technique |
|---|---|
| King + Queen vs King | Drive enemy King to corner, then deliver checkmate with Queen + King |
| King + Rook vs King | Drive enemy King to edge rank/file, deliver checkmate |
| King + 2 Bishops vs King | Drive to corner of bishop color, coordinate checkmate |
| King + Bishop + Knight vs King | Most complex — drive to corner matching bishop color |

## What White Must Avoid
- Stalemate: if Black has NO legal moves and is NOT in check — it's a draw
  - Never leave Black with ONLY the King and no moves, unless it is also in check
- Trading down to an insufficient material position (lone Bishop vs lone Knight = draw)