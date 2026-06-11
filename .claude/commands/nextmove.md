# /project:next-move

Plays exactly one move — delegates to whichever subagent's turn it is.

## Steps
1. Read `game_state/current.json` → check `turn` field
2. If `turn == "white"` → invoke the white-player subagent
3. If `turn == "black"` → invoke the black-player subagent
4. Display the move played and the updated board
5. Report game status (check / checkmate / stalemate / active)

## Usage in Claude Code
```
/project:next-move
```