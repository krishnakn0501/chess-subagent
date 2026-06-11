# /project:show-board

Displays the current board state, whose turn it is, move history, and game status.

## Steps
1. Run `python3 scripts/game_loop.py --show`
2. Read `game_state/current.json` and report:
   - Current board position
   - Whose turn it is
   - Move number
   - Game status (active / check / checkmate / stalemate)
   - Last 5 moves played

## Usage in Claude Code
```
/project:show-board
```