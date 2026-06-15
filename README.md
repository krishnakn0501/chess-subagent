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

## 6. Unnecessary Files & Code Cleanup Recommendations

To maintain a clean, production-ready codebase, the following files/directories should be reviewed and removed or relocated:

### 🗑️ Safe to Delete (Legacy/Redundant)
| Path | Reason |
|------|--------|
| `backend/backend/` | Empty duplicate directory. Likely a path resolution artifact. |
| `IMPLEMENTATION_COMPLETE.md` | Redundant with this README and `SUMMARY.md`. |
| `SUMMARY.md` | Superseded by this comprehensive README. |
| `audit-portfolio.mjs` | Orphaned Node.js script, no references in codebase. |
| `build-frontend.bat` / `build-frontend.sh` | Replaced by standard `npm run build` in `frontend/`. |
| `start-dev.bat` / `start-dev.sh` | Simple wrappers; developers can run `uvicorn` and `npm run dev` directly. |

### 📦 Relocate or Consolidate
| Path | Recommendation |
|------|----------------|
| Root `package.json` / `package-lock.json` / `node_modules/` | Move Playwright dependencies into `frontend/package.json` or a dedicated `e2e-tests/` directory. Root npm packages pollute the workspace. |
| `frontend/playwright-report/` & `frontend/test-results/` | Add to `.gitignore`. These are generated artifacts, not source code. |
| `.claude/commands/*.md` | These are legacy skill definitions. Migrate to `.claude/skills/` or remove if unused. |

### 🧹 Code-Level Cleanup Opportunities
1. **Orchestrator Fallback Logic**: The `_orchestrator_fallback` method is robust but could be extracted into `backend/app/engine/fallback_engine.py` for better separation of concerns.
2. **Coach Agent Prompt Building**: `backend/app/agents/coach_agent.py` has duplicated prompt-building logic that could be templated into a shared utility.
3. **TypeScript Types**: The `WebSocketMessage` type in `frontend/pages/index.tsx` could be moved to a shared `frontend/types/websocket.ts` file for reuse across components.

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

## 10. Deployment

| Component | Target | Notes |
|-----------|--------|-------|
| Frontend | Vercel | `next build` → static export recommended |
| Backend | Railway / EC2 | Requires Stockfish binary on host |
| Stockfish | Pre-installed on server | Set `STOCKFISH_PATH` env var |
| Mem0 ChromaDB | Local filesystem | `backend/data/mem0_storage/` must persist |

### Production Checklist
- [ ] All API keys set as environment variables (never in `.env` committed to git)
- [ ] Stockfish binary downloaded and `STOCKFISH_PATH` configured
- [ ] CORS origins restricted to production frontend URL
- [ ] WebSocket URL updated in frontend to match production backend
- [ ] ChromaDB storage directory has write permissions
- [ ] Node.js and Python dependencies pinned to specific versions

---

## 11. License

MIT

---

*This document serves as the authoritative post-implementation reference for the Claude Code Chess Arena. For development instructions, see [CLAUDE.md](./CLAUDE.md).*