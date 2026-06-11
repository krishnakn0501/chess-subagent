# /project:new-game

Resets the chess board to the starting position and begins a new game between the two subagents.

## Steps
1. Run `python3 scripts/board.py` to reset `game_state/current.json` to the starting position
2. Confirm the board is reset by showing it with `python3 scripts/game_loop.py --show`
3. Tell the user: "New game started. White moves first."
4. Invoke the white-player subagent to make the first move

## Usage in Claude Code
```
/project:new-game
```