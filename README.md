# Claude Code Chess Arena

A real-time chess game where two AI sub-agents play against each other, built with a modular FastAPI backend and Next.js frontend with WebSocket streaming.

## Features

- **Two AI Agents**: White plays classical chess, Black plays dynamic Sicilian Defence
- **Real-time Updates**: WebSocket streaming for instant board updates (replaces legacy 2-second polling)
- **Automated Gameplay**: Start, pause, stop, reset, and step through moves
- **Modern UI**: Clean Next.js interface with react-chessboard visualization
- **Modular Architecture**: Clean separation between backend API, engine logic, and frontend presentation

---

## Project Structure

```
claude-project/
├── backend/                          # Python FastAPI backend server
│   ├── app/
│   │   ├── __init__.py              # Application package marker
│   │   ├── main.py                  # FastAPI entrypoint with WebSocket & REST endpoints
│   │   ├── orchestrator.py          # Automated game execution loop controller
│   │   ├── core/                    # Core utilities and infrastructure
│   │   │   ├── __init__.py
│   │   │   ├── config.py            # Path constants and game configuration
│   │   │   └── connection.py        # WebSocket ConnectionManager
│   │   └── engine/                  # Chess engine modules
│   │       ├── __init__.py
│   │       ├── board.py             # Board representation, FEN parsing, state persistence
│   │       ├── validate_move.py     # Full chess rule validation
│   │       ├── apply_move.py        # Move application with broadcast hooks
│   │       └── get_legal_moves.py   # Legal move generation
│   └── requirements.txt             # Python dependencies (fastapi, uvicorn, pydantic)
│
├── frontend/                         # Next.js TypeScript React frontend
│   ├── pages/                       # Pages Router components
│   │   ├── _app.tsx                 # App wrapper with global styles
│   │   └── index.tsx                # Main UI with WebSocket consumer
│   ├── styles/                      # Global CSS and Tailwind configuration
│   │   └── globals.css
│   ├── next.config.js               # Next.js configuration with API proxy
│   ├── package.json                 # Node.js dependencies
│   ├── tsconfig.json                # TypeScript compiler options
│   ├── postcss.config.js            # PostCSS configuration
│   └── tailwind.config.js           # Tailwind CSS customization
│
├── .claude/scripts/                  # Claude Code agent scripts (sub-agents)
│   ├── white_player/                # White AI player
│   │   ├── choose_move.py           # Decision-making entry point
│   │   └── evaluate.py              # Position evaluation function
│   └── black_player/                # Black AI player
│       ├── choose_move.py           # Decision-making entry point
│       └── evaluate.py              # Position evaluation function
│
├── game_state/                       # Persistent game data
│   ├── current.json                 # Current game position and state
│   └── last_game.pgn                # PGN export of last completed game
│
├── CLAUDE.md                         # Project instructions for Claude Code
├── architecture.md                   # Detailed technical architecture documentation
├── FRONTEND.md                       # Frontend-specific documentation
├── README.md                         # This file - user-facing quickstart guide
└── *.sh / *.bat                      # Cross-platform development/build scripts
```

**Root Directory Contents:** Only `backend/`, `frontend/`, `.claude/`, and `game_state/` directories plus global scripts and documentation files. No stray frontend artifacts or legacy engine folders remain at project root level.

---

## Quick Start

### Prerequisites

- Python 3.11+ with pip
- Node.js 18+ with npm/yarn
- Bash shell (Git Bash, WSL, or native on macOS/Linux)

### 1. Install Backend Dependencies

```bash
cd backend
pip install -r requirements.txt
```

Backend requires:
- `fastapi>=0.109.0` - Web framework
- `uvicorn[standard]>=0.27.0` - ASGI server
- `websockets>=12.0` - WebSocket protocol support
- `pydantic>=2.5.0` - Data validation

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
```

Frontend requires:
- `next@14.0.0` - React framework
- `react-chessboard@^4.6.0` - Chessboard component
- `chess.js@^1.0.0-beta.8` - Chess rules library
- `tailwindcss` - Utility-first CSS framework

### 3. Start the Backend Server

From **project root**:

```bash
cd backend


```

Or using the helper script:
```bash
./start-dev.sh backend    # macOS/Linux
.\start-dev.bat backend   # Windows
```

The backend runs at http://localhost:8000

### 4. Start the Frontend

From **project root**:

```bash
cd frontend
npm run dev
```

Or using the helper script:
```bash
./start-dev.sh frontend   # macOS/Linux
.\start-dev.bat frontend  # Windows
```

The frontend runs at http://localhost:3000 with automatic API proxy to backend.

### 5. Access the Application

Open your browser to **http://localhost:3000**

You should see:
- A clean chessboard in starting position
- Turn indicator showing "White to move"
- Agent profiles for both players
- Controls: Start Simulation, Pause, Reset Simulation, Reset Board
- Move log and PGN history sections

---

## How It Works

### Real-Time Event Pipeline

Unlike traditional REST polling, this system uses **WebSocket streaming** for instantaneous updates:

1. **Connection Phase**: Browser opens WebSocket to `/ws/game` on page load
2. **Initial State**: Server immediately sends full game state (`type: initial_state`)
3. **Game Loop**: When automated mode starts, orchestrator runs continuously:
   ```
   Load state → Choose agent (white/black) → Execute subprocess → Parse output
   → Broadcast {type: move_complete, state, agent_output} → Sleep(1s)
   ```
4. **UI Updates**: Frontend receives messages and updates React state instantly
5. **User Control**: Buttons call `/api/control` which triggers corresponding orchestrator methods

### Agent Subprocess Execution

Agent scripts run as isolated processes via the orchestrator:

```python
# From backend/app/orchestrator.py
process = await asyncio.create_subprocess_exec(
    sys.executable,
    str(agent_script),              # .claude/scripts/{color}_player/choose_move.py
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    env={**os.environ, "PYTHONPATH": f"{engine_path}:{new_engine_path}"}
)
```

**Key Points:**
- PYTHONPATH includes `.claude/scripts/` and `backend/app/engine/` for correct module resolution
- Timeout: 60 seconds per move
- Output format: `WHITE_MOVE: e2e4` + `REASON: <explanation>`

### Shared Game State

All components read/write exclusively through `game_state/current.json`:

| Component | Reads | Writes |
|-----------|-------|--------|
| Agent Scripts | ✅ Current position | ✅ Move results |
| Backend Engine | ✅ Board state | ✅ Updated board |
| Orchestrator | ✅ Status/clocks | ✅ New moves |
| Frontend (WebSocket) | ✅ Initial state | ❌ Passive only |

---

## API Reference

### REST Endpoints

#### Health Check

```bash
curl http://localhost:8000/api/health
# Response: {"status":"ok","message":"Chess Arena API is running"}
```

#### Server Status

```bash
curl http://localhost:8000/api/status
# Response: {"status":"healthy","websocket_clients":N,"game_running":bool,"game_paused":bool}
```

#### Get Current Game State (Legacy)

```bash
curl http://localhost:8000/api/game-state
```

#### Control Commands

**Start Automated Game:**
```bash
curl -X POST http://localhost:8000/api/control \
  -H "Content-Type: application/json" \
  -d '{"command": "start"}'
```

**Pause/Resume:**
```bash
curl -X POST http://localhost:8000/api/control \
  -H "Content-Type: application/json" \
  -d '{"command": "pause"}'
```

**Reset Game:**
```bash
curl -X POST http://localhost:8000/api/control \
  -H "Content-Type: application/json" \
  -d '{"command": "reset"}'
```

**Step Single Move:**
```bash
curl -X POST http://localhost:8000/api/control \
  -H "Content-Type: application/json" \
  -d '{"command": "step"}'
```

### WebSocket Protocol (`/ws/game`)

**Message Types:**

```typescript
// Client → Server (heartbeats)
{ "type": "ping" }

// Server → Client (initial connection)
{ "type": "initial_state", "state": GameState }

// Server → Client (after each move)
{ 
  "type": "move_complete",
  "state": GameState,
  "agent_output": {
    "success": true,
    "output": "WHITE_MOVE: e2e4\r\nREASON: Open the center...",
    "error": ""
  }
}

// Server → Client (on reset)
{ "type": "reset", "state": GameState }
```

**Connecting from Browser:**

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/game');

ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  if (msg.type === 'move_complete') {
    setGameState(msg.state);
    console.log('Move executed:', msg.agent_output.output);
  }
};

ws.onerror = (err) => console.error('WebSocket error', err);
```

---

### Key Design Decisions

1. **Separation of Concerns**: Backend (API), engine (logic), frontend (presentation) fully decoupled
2. **Subprocess Isolation**: Agents execute outside Python process boundary, preventing crashes
3. **State File Persistence**: `current.json` serves as single source of truth
4. **Consolidated Architecture**: All engine logic unified in `backend/app/engine/`; legacy folders removed
5. **No Root Pollution**: All frontend configs moved to `frontend/`; root contains only essential directories

---

## Troubleshooting

### Frontend Won't Load

1. Ensure backend is running: `curl http://localhost:8000/api/health`
2. Check browser DevTools Network tab for WebSocket connection status
3. Verify `frontend/next.config.js` has correct proxy rewrites

### WebSocket Not Connecting

1. Backend must be accessible at `http://localhost:8000`
2. CORS settings allow origins: check `backend/app/main.py` CORS middleware
3. Firewall not blocking port 8000

### Agent Moves Not Appearing

1. Check backend logs for subprocess errors
2. Verify `.claude/scripts/white_player/choose_move.py` executes standalone:
   ```bash
   python .claude/scripts/white_player/choose_move.py
   ```
3. Confirm PYTHONPATH includes `backend/app/engine/` directory

### Duplicate Move Logs

The frontend now properly handles `agent_output` as an object `{success, output, error}` rather than raw string, eliminating duplicate logging issues.

---

## Development Workflow

### Recommended Approach

1. Keep terminal open for backend: `uvicorn app.main:app --reload`
2. Open second terminal for frontend: `npm run dev`
3. Use hot reload during development (changes auto-restart servers)

### Building for Production

**Backend:**
```bash
# Package as wheel or deploy directly
cd backend && pip install wheel && python setup.py bdist_wheel
```

**Frontend:**
```bash
cd frontend
npm run build
npm start  # Serves static build
```

Note: For production deployment, consider building static exports instead of Next.js server mode.

---

## License

MIT

---


