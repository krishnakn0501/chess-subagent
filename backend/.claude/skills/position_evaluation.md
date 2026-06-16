# SKILL: Chess Position Evaluation

## When to use this skill
Load this skill when either subagent needs to evaluate a chess position and choose the best move.
Triggered when working in `scripts/white-player/evaluate.py` or `scripts/black-player/evaluate.py`.

## What good position evaluation looks like

### Step 1 — Immediate threats (non-negotiable, check first)
Before anything else, ask:
- Am I in check? → MUST resolve (King move, block, or capture attacker)
- Can I checkmate in 1? → Always play it
- Is any of my pieces hanging (attacked and undefended)? → Protect or move it

### Step 2 — Material gain
Score captures using MVV-LVA (Most Valuable Victim - Least Valuable Attacker):
```
Capture value = victim_value × 10 - attacker_value

Examples:
  Pawn takes Queen  = 9×10 - 1  = +89   ← always do this
  Queen takes Pawn  = 1×10 - 9  = +1    ← only if safe
  Knight takes Bishop = 3×10 - 3 = +27  ← good trade
```
Piece values: Q=9  R=5  B=3  N=3  P=1

### Step 3 — Tactical patterns (look for these every move)
| Pattern | Description | Example signal |
|---|---|---|
| Fork | One piece attacks two enemy pieces | Knight on f7 attacks King + Rook |
| Pin | Piece can't move without exposing higher-value piece | Bishop pins Knight to King |
| Skewer | High-value piece must move, exposing piece behind | Rook attacks Queen, Bishop behind |
| Discovered attack | Moving piece A unleashes piece B's attack | Move Knight, Bishop attacks Queen |
| Back-rank mate | Rook/Queen delivers checkmate on opponent's back rank | Rg8# |
| Zwischenzug | Ignore recapture, play stronger intermediate move first | Ignore captured pawn, deliver check |

### Step 4 — Positional factors (when no tactics available)
Score these in order of importance:

**King Safety** (highest positional priority)
- Castled King with pawn shelter = safe
- King in center during middlegame = dangerous (-20 penalty)
- Open files toward your King = vulnerable

**Piece Activity**
- Rooks on open files (no pawns blocking): +6
- Rooks on 7th rank (behind enemy pawns): +8
- Knight on outpost square (enemy can't chase it with pawns): +5
- Bishop with open diagonal: +4
- Queen active but safe: +3

**Pawn Structure**
- Passed pawn (no enemy pawns blocking or flanking): very valuable, +8–15 depending on advancement
- Connected pawns: +2
- Isolated pawn (no friendly pawns on adjacent files): -3
- Doubled pawns: -2

**Center Control**
- Piece or pawn on/attacking e4, d4, e5, d5: +2 per square controlled

### Step 5 — Game phase adjustments

**Opening (moves 1–12)**
- Bonus: +4 for each undeveloped minor piece that gets developed
- Bonus: +20 for castling (king safety priority)
- Penalty: -5 for moving same piece twice before others are developed
- Penalty: -8 for early Queen development

**Middlegame (moves 13–30)**
- Full evaluation as above
- Extra weight on King attack if opponent's King is exposed

**Endgame (30+ moves or few pieces left)**
- King activation is NOW positive: +3 per square closer to center
- Passed pawn push: score = (rank advancement)² × 2
- Rook behind passed pawn: +10
- Simplify if winning: trade pieces (not pawns)

## How subagents use this skill

When Claude Code is asked to evaluate a position, it should:
1. Call `python3 scripts/get_legal_moves.py <color>` to get all legal moves
2. For each candidate move, mentally apply Steps 1–5 above
3. Pick the move with the highest total score
4. If scores are very close (within 3 points), prefer the move that:
   - Keeps more options open
   - Does not weaken King safety
   - Improves the worst-placed piece

## Output format expected by choose_move.py
```
CHOSEN_MOVE: e2e4
REASON: Controls the center and opens lines for bishop and queen development
```