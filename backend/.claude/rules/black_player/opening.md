---
paths:
  - scripts/black-player/choose_move.py
  - scripts/black-player/evaluate.py
---

# Black Player — Opening Rules (Moves 1–10)

## Core Philosophy
Black plays the **Sicilian Defence** — fight for the center asymmetrically, create imbalances, seek counterplay on the queenside while White attacks kingside.

## Response Tree
| White plays | Black responds | Move |
|---|---|---|
| `e2e4` | Sicilian: c5 challenges d4, not e4 | `c7c5` |
| `d2d4` | King's Indian: fianchetto kingside | `g8f6` then `g7g6` |
| `c2c4` | English: mirror with `e7e5` | `e7e5` |
| anything else | Develop `g8f6` — most flexible | `g8f6` |

## Sicilian Development Order (after 1.e4 c5)
1. `g8f6` — develop Knight, pressure e4
2. `d7d6` or `e7e6` — control center, open diagonal for bishop
3. `b8c6` or `a7a6` — fight for d4
4. Castle kingside (`e8g8`) OR delay and castle queenside for sharpness
5. Launch queenside counterattack: `b7b5`, `a7a5` pawn storm

## What NOT to do in the Opening
- Do NOT passively mirror White's every move — Black needs counterplay, not equality
- Do NOT castle queenside too early if your queenside pawns are already advanced
- Do NOT trade your dark-squared Bishop in Sicilian positions — it is your best defender
- Do NOT exchange off pieces if you are under attack — keep tension