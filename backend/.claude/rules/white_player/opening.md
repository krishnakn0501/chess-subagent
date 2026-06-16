---
paths:
  - scripts/white-player/choose_move.py
  - scripts/white-player/evaluate.py
---

# White Player — Opening Rules (Moves 1–10)

## Preferred Opening
White always opens with **1. e4** (King's Pawn Opening) — move `e2e4`.

## Priority Tree (in order)
1. If move 1 and no moves played → play `e2e4`
2. Develop Knights before Bishops: `g1f3` then `b1c3`
3. Control center with pawns: e4, d4 are ideal
4. Castle kingside as early as possible (`e1g1`) — safety first
5. Connect Rooks by clearing back rank

## Responses to Black's Common Defenses
| Black plays | White should respond |
|---|---|
| `e7e5` (Open Game) | `g1f3` (attack e5), then `f1c4` (Italian) |
| `c7c5` (Sicilian) | `g1f3`, then `d2d4` to open the center |
| `e7e6` (French) | `d2d4` to claim center space |
| `c7c6` (Caro-Kann) | `d2d4` to maintain center |

## What NOT to do in the Opening
- Do NOT move the same piece twice before developing all minor pieces
- Do NOT bring the Queen out before move 5 (becomes a target)
- Do NOT move flank pawns (a, h) in the opening
- Do NOT castle queenside unless forced — it exposes the King to center files