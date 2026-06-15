# Claude Code Chess Arena

A real-time, multi-agent chess simulation where two AI sub-agents (White and Black) play against each other, orchestrated by a FastAPI backend with WebSocket streaming, Stockfish evaluation, Critic analysis, and a RAG-based Coach chatbot.

> **Document Type**: Post-Implementation Architecture & Requirements Document  
> **Last Updated**: June 2026  
> **Version**: 2.0 (Token-Optimized, Async-Decoupled, RAG-Enhanced)

---

## 1. System Overview & Goals

### Core Objectives
- **Autonomous Gameplay**: Two Claude Code sub-agents make decisions based on position context, LTM (Long-Term Memory), and strategic identity.
- **Real-Time Observability**: Instant UI updates via WebSocket streaming (no polling).
- **Self-Improvement Loop**: Critic Agent analyzes moves, extracts lessons, and stores them in Mem0 (ChromaDB) for future reference.
- **Intelligent Coaching**: RAG-based Coach Agent answers user queries about general chess strategy and current-game predictions.
- **Low Latency**: Token-based agent outputs eliminate JSON parsing overhead; async critic decoupling prevents UI blocking.

---

## 2. System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (Next.js)                               │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────────────┐ │
│  │ Chessboard UI   │  │ Move / PGN Log   │  │ Coach Chatbot (Floating)   │ │
│  │ (react-chess)   │  │ + Win Prob Bar   │  │ + Critic Annotations       │ │
│  └────────┬────────┘  └─────────┬────────┘  └─────────────┬──────────────┘ │
│           │                     │                        │                  │
│           └────────── WebSocket (ws://localhost:8000/ws/game) ────────────┘ │
│                      REST API (http://localhost:8000/api/...)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│                         BACKEND (FastAPI / Python)                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │ main.py          │  │ orchestrator.py  │  │ coach_agent.py           │  │
│  │ - WS Manager     │  │ - Game loop      │  │ - Query rewriting        │  │
│  │ - CORS / Routes  │  │ - Subprocess mgmt│  │ - Mem0 semantic search   │  │
│  │ - /api/coach     │  │ - Async critic   │  │ - LLM answer synthesis   │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────────┬─────────────┘  │
│           │                     │                         │                 │
│  ┌────────▼─────────────────────▼─────────────────────────▼─────────────┐  │
│  │                        ENGINE MODULES                                │  │
│  │  board.py │ validate_move.py │ apply_move.py │ get_legal_moves.py   │  │
│  │  stockfish_evaluator.py (centipawn → win prob + PV line)            │  │
│  │  memory_manager.py (Mem0 ChromaDB + JSON fallback)                  │  │
│  └──────────────────────────────┬───────────────────────────────────────┘  │
└─────────────────────────────────┼──────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼──────────────────────────────────────────┐
│                         AI AGENT SUBPROCESSES (.claude/scripts/)           │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐ │
│  │ white_player/        │  │ black_player/        │  │ critic_agent/    │ │
│  │ choose_move.py       │  │ choose_move.py       │  │ choose_move.py   │ │
│  │ [MOVE] + [REASON]    │  │ [MOVE] + [REASON]    │  │ TOON pipe-format │ │
│  └──────────┬───────────┘  └──────────┬───────────┘  └────────┬─────────┘ │
│             │                         │                       │           │
│             └───────────┬─────────────┴───────────────┬───────┘           │
│                         ▼                             ▼                   │
│                 ┌───────────────┐             ┌───────────────┐           │
│                 │ Anthropic API │             │ Qwen/DashScope│           │
│                 │ (claude-sonnet│             │ (qwen3.7-max) │           │
│                 └───────────────┘             └───────────────┘           │
└────────────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼──────────────────────────────────────────┐
│                         PERSISTENCE & EXTERNAL                             │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐ │
│  │ game_state/          │  │ backend/data/        │  │ backend/bin/     │ │
│  │ current.json         │  │ mem0_storage/        │  │ stockfish.exe    │ │
│  │ last_game.pgn        │  │ fallback_lessons.json│  │                  │ │
│  └──────────────────────┘  └──────────────────────┘  └──────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 2a. Architecture: Three-Way Microservices Deployment (Updated 2026)

This project uses a **three-way microservices deployment architecture**:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                    FRONTEND (Vercel Project A - Next.js)                │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────┐    │
│  │ Chessboard UI   │  │ Move / PGN Log   │  │ Coach Chatbot      │    │
│  │ (react-chess)   │  │ + Win Prob Bar   │  │ (Floating)         │    │
│  └────────┬────────┘  └─────────┬────────┘  └──────────┬─────────┘    │
│           │                     │                      │               │
│           └─────────────────────┴──────────────────────┘               │
│                         │                                               │
│         NEXT_PUBLIC_BACKEND_URL → Railway                               │
│         NEXT_PUBLIC_WS_URL → Railway (wss://)                           │
│         NEXT_PUBLIC_ENGINE_URL → Vercel Project B                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼─────────────────────────────────────┐
        │                           │                                     │
        ▼                           ▼                                     │
┌────────────────────┐    ┌──────────────────────────────────────────────┐│
│ ENGINE (Vercel     │    │              BACKEND (Railway)               ││
│ Project B)         │    │              (FastAPI Python)                ││
│ Serverless Node.js │    │                                              ││
│                    │    │  ┌──────────────────┐  ┌──────────────────┐ ││
│ api/evaluate.js    │◄───┤│  │ main.py          │  │ orchestrator.py  │ ││
│ POST {fen, depth}  │    ││  │ - WS Manager     │  │ - Game loop      │ ││
│ {best_move, cp}    │    ││  │ - CORS / Routes  │  │ - Subprocess mgmt│ ││
│                    │    ││  │ - /api/coach     │  │ - Async critic   │ ││
│ CORS: "*"          │    ││  └────────┬─────────┘  └────────┬─────────┘ ││
│ Max Duration: 10s  │    ││           │                     │           ││
└────────────────────┘    ││  ┌─────────▼─────────────────────▼───────────┐││
                          ││  │                        ENGINE MODULES     │││
                          ││  │  board.py │ validate_move.py             │││
                          ││  │  apply_move.py │ get_legal_moves.py      │││
                          ││  │  stockfish_evaluator.py (HTTP client)    │││
                          ││  │  memory_manager.py (Mem0 ChromaDB)       │││
                          ││  └───────────────────────────────────────────┘││
                          │└──────────────────────────────────────────────┘│
                          └────────────────────────────────────────────────┘
```

### Why Not All-on-Vercel?

Vercel functions are short-lived (max 10s-900s) and don't support persistent WebSocket connections. The Chess Arena's real-time game loop relies on long-living WebSocket connections between frontend and backend orchestrator, which requires a dedicated server like Railway or EC2.

---

## Monorepo Structure

```
project-root/
├── frontend/              # Next.js UI (deploy to Vercel Project A)
│   ├── pages/
│   │   ├── index.tsx      # Main chess arena UI with WebSocket consumer
│   │   └── _app.tsx       # App wrapper
│   ├── components/        # React components (CoachChatbot, etc.)
│   ├── styles/            # Tailwind CSS globals
│   ├── public/            # Static assets
│   ├── package.json
│   ├── next.config.js
│   ├── vercel.json        # Minimal Vercel config (no API routes)
│   └── .env.local         # NEXT_PUBLIC_BACKEND_URL, NEXT_PUBLIC_ENGINE_URL
│
├── engine/                # Stockfish microservice (deploy to Vercel Project B)
│   ├── api/
│   │   └── evaluate.js    # Serverless Stockfish endpoint
│   ├── package.json       # stockfish npm dependency
│   └── vercel.json        # Vercel function config with CORS headers
│
├── backend/               # FastAPI Python backend (deploy to Railway)
│   ├── app/
│   │   ├── main.py        # FastAPI entrypoint with WebSocket & REST
│   │   ├── orchestrator.py# Game loop controller
│   │   ├── core/          # ConnectionManager, config
│   │   ├── engine/        # Board logic, move validation, stockfish client
│   │   └── agents/        # Coach agent, critic scripts references
│   ├── game_state/        # Runtime JSON state (gitignored)
│   ├── data/              # Mem0 storage, fallback lessons
│   ├── requirements.txt
│   ├── Procfile           # Railway deployment config
│   └── .env.example       # ENGINE_URL env var template
│
├── .claude/               # Agent scripts & rules for sub-agents
│   ├── scripts/
│   │   ├── white_player/  # White agent choose_move.py, evaluate.py
│   │   ├── black_player/  # Black agent (Sicilian focus)
│   │   └── critic_agent/  # Move quality analyzer
│   ├── rules/             # Chess domain knowledge per agent
│   └── settings.json      # API keys, model configs
│
├── docs/                  # Architecture documentation
├── CLAUDE.md              # Project brain / development guide
├── README.md              # This file
└── .gitignore             # Updated for 3-way structure
```

### Environment Variables (Updated 2026)

**Frontend (`frontend/.env.local`):**
```env
# Backend API URL (FastAPI on Railway)
NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app

# WebSocket URL (same host as backend)
NEXT_PUBLIC_WS_URL=wss://your-backend.railway.app

# Stockfish Engine URL (Vercel Project B)
NEXT_PUBLIC_ENGINE_URL=https://your-engine.vercel.app
```

**Backend (`backend/.env`):**
```env
# Stockfish Engine URL (points to Vercel Project B)
ENGINE_URL=https://your-engine.vercel.app

# LLM API Keys
ANTHROPIC_API_KEY=your_key
CRITIC_AGENT_API_KEY=your_qwen_key
# ... other API keys
```

**Engine (`engine/.env`):**
```env
# No env vars needed for pure serverless Stockfish function
```

---

## 3. Tech Stack & Status

| Layer | Technology | Status | Notes |
|-------|------------|--------|-------|
| **Frontend Framework** | Next.js 14 (Pages Router) | ✅ Stable | TypeScript, Tailwind CSS |
| **UI Components** | react-chessboard, lucide-react | ✅ Stable | Responsive, mobile-first |
| **Backend Framework** | FastAPI + Uvicorn | ✅ Stable | Async-first, CORS configured |
| **Chess Engine** | python-chess + Stockfish 16 | ✅ Stable | Depth 15 analysis, PV extraction |
| **LLM Provider** | Anthropic (Sonnet 4.6) + Qwen (DashScope) | ✅ Stable | Subagents use Sonnet, Critic uses Qwen |
| **Vector DB / LTM** | Mem0 (ChromaDB) + JSON fallback | ✅ Stable | Semantic search for lessons |
| **Real-time Comms** | Native WebSocket API | ✅ Stable | Auto-reconnect, ping/pong heartbeats |
| **Testing** | Playwright | 🟡 Partial | E2E tests exist, needs expansion |

---

## 4. Data Flow & Event Pipeline

### 4.1. The Game Loop (Per Move)
1. **Orchestrator** loads `game_state/current.json`.
2. **Agent Subprocess** is spawned with position context + LTM lessons.
3. **Agent** outputs `[MOVE]\n<move>\n[REASON]\n<one-line reason>` (Token format).
4. **Orchestrator** applies move via `engine/apply_move.py`.
5. **Stockfish** evaluates new position → win probabilities + PV line.
6. **WebSocket** IMMEDIATELY broadcasts `{type: "move_complete", state, win_probabilities, pv_line}`.
7. **Critic Task** spawns asynchronously (`asyncio.create_task`).
8. **Game Loop** waits up to 15s max for critic (bounded wait via `asyncio.wait`), then proceeds to next move.
9. **Critic** (when ready) broadcasts `{type: "critic_update", move, color, critic_commentary}`.
10. **Memory Manager** stores lesson if sentiment is POSITIVE or NEGATIVE.

### 4.2. Agent Output Formats (Strict Enforcement)

#### Player Agents (White & Black)
```text
[MOVE]
e2e4
[REASON]
Controls the center and opens lines for the bishop and queen.
```
*Orchestrator parses this via regex/line-matching. No JSON.*

#### Critic Agent
```text
sentiment|POSITIVE|explanation|Stockfish predicts Nf3 revealing strong center control|lesson|Always develop knights before pushing flank pawns
```
*Single pipe-delimited line. Keys: `sentiment`, `explanation`, `lesson`. No JSON, no brackets, no markdown.*

---

## 5. API & WebSocket Reference

### REST Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/status` | Orchestrator state + WS client count |
| `GET` | `/api/game-state` | Current board state (legacy, prefer WS) |
| `POST`| `/api/control` | `{command: "start"\|"stop"\|"pause"\|"reset"\|"step"}` |
| `POST`| `/api/coach` | `{query: "string", fen: "string" (optional)}` |

### WebSocket Messages (`/ws/game`)
| Type | Direction | Payload |
|------|-----------|---------|
| `initial_state` | Server → Client | `{state: GameState}` |
| `move_complete` | Server → Client | `{state, agent_output, win_probabilities, pv_line}` |
| `critic_update` | Server → Client | `{critic_commentary, move, color, timestamp}` |
| `reset` | Server → Client | `{state}` |
| `ping`/`pong` | Bidirectional | Keep-alive |

---

## 6. Cleanup Status

The following files/directories have been **cleaned up** as part of the microservices migration:

### ✅ Completed (Already Removed/Relocated)
| Path | Action |
|------|--------|
| Root `node_modules/` / `package-lock.json` | Deleted — dependencies now isolated per project |
| `backend/api/evaluate.js` | Moved to `engine/api/evaluate.js` |
| `Procfile` (root) | Moved to `backend/Procfile` |
| `frontend/pages/api/proxy/` | Deleted — direct URL routing via env vars |
| `frontend/vercel.json` (old config) | Simplified — no API routes needed |

### 🗑️ Safe to Delete (Legacy/Redundant - Optional)
| Path | Reason |
|------|--------|
| `backend/backend/` | Empty duplicate directory (if exists). |
| `IMPLEMENTATION_COMPLETE.md` | Redundant with this README. |
| `SUMMARY.md` | Superseded by this comprehensive README. |
| `audit-portfolio.mjs` | Orphaned Node.js script, no references. |
| `build-frontend.bat` / `build-frontend.sh` | Replaced by standard `npm run build`. |
| `start-dev.bat` / `start-dev.sh` | Simple wrappers; use uvicorn/npm directly. |

### 🧹 Code-Level Recommendations
1. **Orchestrator Fallback Logic**: Could be extracted into `backend/app/engine/fallback_engine.py`.
2. **TypeScript Types**: Consider moving `WebSocketMessage` type to `frontend/types/websocket.ts`.

---

## 7. Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| **Frontend shows "Connection error"** | Backend not running or port 8000 blocked | Run `uvicorn app.main:app --reload` in `backend/`. Check firewall. |
| **Agent outputs "NOT_MY_TURN"** | Orchestrator state desync | Send `POST /api/control` with `{"command": "reset"}`. |
| **Critic analysis always NEUTRAL** | API key missing or TOON parsing failed | Check `CRITIC_AGENT_API_KEY` in `.env`. Verify orchestrator logs for `[Critic] Parsed TOON format successfully`. |
| **Coach answers "outside my domain"** | Query lacks chess keywords | Coach is designed to reject non-chess queries. Rephrase with chess terminology. |
| **Mem0 storage fails silently** | ChromaDB path permissions or missing API keys | Check `MEM0_QWEN_API_KEY` and `EMBEDDINGS_API_KEY` in `.env`. Verify `backend/data/mem0_storage/` is writable. |

---

## 8. Development Workflow

### Local Development
```bash
# Terminal 1: Backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

### Environment Variables (`.env` at project root)
```env
# LLM APIs
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-sonnet-4-6

# Critic Agent (Qwen via DashScope)
CRITIC_AGENT_API_KEY=your_qwen_key
CRITIC_API_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
CRITIC_MODEL=qwen3.7-max

# Mem0 / Embeddings
MEM0_QWEN_API_KEY=your_qwen_key
MEM0_QWEN_API_URL=https://dashscope-intl.aliyuncs.com/compatible-mode
MEM0_QWEN_MODEL_NAME=qwen-plus
EMBEDDINGS_API_KEY=your_embeddings_key
EMBEDDINGS_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode
EMBEDDINGS_MODEL_NAME=text-embedding-v1

# Stockfish
STOCKFISH_PATH=backend/bin/stockfish
```

> **Note**: Never hardcode secrets in source files. All keys load via `python-dotenv` or Next.js environment config.

---

## 9. Verification & Testing

### Manual End-to-End Verification

```bash
# 1. Backend health
curl http://localhost:8000/api/health
# Expected: {"status":"ok","message":"Chess Arena API is running"}

# 2. Start a game and watch WebSocket messages
# Open browser to http://localhost:3000, click "Start Simulation"

# 3. Test Coach Agent
curl -X POST http://localhost:8000/api/coach \
  -H "Content-Type: application/json" \
  -d '{"query": "What is a fork in chess?"}'
# Expected: General chess explanation about fork tactic

# 4. Test Coach Prediction
curl -X POST http://localhost:8000/api/coach \
  -H "Content-Type: application/json" \
  -d '{"query": "Who will win?", "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"}'
# Expected: Position analysis with prediction reasoning

# 5. Test Coach out-of-domain rejection
curl -X POST http://localhost:8000/api/coach \
  -H "Content-Type: application/json" \
  -d '{"query": "Tell me about Python programming"}'
# Expected: "This is outside my domain" response

# 6. Verify critic TOON format in logs
# Start a game and check backend logs for:
#   "[Critic] Parsed TOON format successfully"
```

### Automated Tests
- **Frontend E2E**: Playwright tests in `frontend/tests/`
- **Backend**: pytest integration (to be expanded)

---

## 10. Deployment (Three-Way Microservices)

| Component | Target Project | Build Command | Notes |
|-----------|---------------|---------------|-------|
| **Frontend** | Vercel Project A | `next build` | Deploy from `frontend/` directory |
| **Engine** | Vercel Project B | Node.js serverless | Deploy from `engine/` directory |
| **Backend** | Railway / EC2 | `uvicorn app.main:app` | Persistent server for WebSocket |

### Vercel Project Configuration

**Project A (Frontend):**
- Root Directory: `frontend`
- Build Command: `npm run build`
- Output Directory: `.next`
- Environment Variables: `NEXT_PUBLIC_BACKEND_URL`, `NEXT_PUBLIC_ENGINE_URL`

**Project B (Engine):**
- Root Directory: `engine`
- Framework Preset: Other (serverless function)
- No build step needed — pure Node.js API routes

### Railway Deployment (Backend)

```bash
# Connect your repo to Railway
railway link

# Deploy backend service (from root, Railway will detect Procfile)
railway up --path backend

# Set environment variables
railway variables set ENGINE_URL=https://your-engine.vercel.app
railway variables set ANTHROPIC_API_KEY=...
```

### Production Checklist
- [ ] Frontend env vars configured in Vercel Project A dashboard
- [ ] Engine deployed to Vercel Project B with correct CORS headers
- [ ] Backend ENV vars set in Railway dashboard (`ENGINE_URL`, API keys)
- [ ] CORS origins restricted in production (backend/main.py)
- [ ] All three projects can reach each other over HTTPS

---

## 11. License

MIT

---

*This document serves as the authoritative post-implementation reference for the Claude Code Chess Arena. For development instructions, see [CLAUDE.md](./CLAUDE.md).*