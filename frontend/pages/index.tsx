// pages/index.tsx
import React, { useState, useEffect, useRef } from 'react';
import { Chessboard } from 'react-chessboard';
import CoachChatbot from '../components/CoachChatbot';

// Type definitions for WebSocket messages
type AgentOutput = {
  success: boolean;
  output: string;
  error: string;
};

type CriticCommentary = {
  sentiment: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';
  explanation: string;
  lesson: string;
  move?: string;
  color?: string;
  timestamp?: number;
};

type WinProbabilities = {
  white: number;
  black: number;
};

type WebSocketMessage = {
  type: 'initial_state' | 'move_complete' | 'critic_update' | 'reset' | 'error';
  state?: GameState;
  agent_output: AgentOutput | string | null;
  win_probabilities?: WinProbabilities;
  critic_commentary?: CriticCommentary | null;
  pv_line?: string[];
  move?: string;
  color?: string;
  fen_after?: string;
  timestamp?: number;
};

// Type definitions
type GameState = {
  board: string[][];
  turn: string;
  castling: {
    white_kingside: boolean;
    white_queenside: boolean;
    black_kingside: boolean;
    black_queenside: boolean;
  };
  en_passant: string | null;
  halfmove_clock: number;
  fullmove_number: number;
  move_history: Array<{
    move: string;
    color: string;
    piece: string;
    from: string;
    to: string;
    captured: string | null;
    check: boolean;
    fullmove: number;
  }>;
  status: string;
  in_check: string | null;
};

type Settings = {
  env?: {
    CLAUDE_CODE_SUBAGENT_MODEL?: string;
    ANTHROPIC_DEFAULT_SONNET_MODEL?: string;
  };
};

type AgentProfile = {
  name: string;
  model: string;
  temperament: string;
};

type UIStatus = {
  state: 'idle' | 'thinking' | 'analyzing' | 'connecting' | 'error';
  message: string;
  player?: 'white' | 'black';
};

const HomePage: React.FC = () => {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(true);
  const [moveLog, setMoveLog] = useState<string[]>([]);
  const [agentOutput, setAgentOutput] = useState<string>('');
  const lastMoveCountRef = useRef<number>(0);
  const [whiteProfile, setWhiteProfile] = useState<AgentProfile>({
    name: 'White Player',
    model: 'Claude Sonnet 4.6',
    temperament: 'Classical, principled chess with opening book preferences'
  });
  const [blackProfile, setBlackProfile] = useState<AgentProfile>({
    name: 'Black Player',
    model: 'Claude Sonnet 4.6',
    temperament: 'Dynamic, counterattacking chess with Sicilian Defence focus'
  });

  // New state for enhanced features
  const [winProbabilities, setWinProbabilities] = useState<WinProbabilities>({ white: 50, black: 50 });
  const [criticCommentary, setCriticCommentary] = useState<CriticCommentary[]>([]);
  const [pvLine, setPvLine] = useState<string[]>([]);
  const [uiStatus, setUiStatus] = useState<UIStatus>({ state: 'idle', message: 'Ready' });

  // Base URL for the FastAPI Backend (from env var with fallback for local dev)
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  // Initialize game state on load (initial fetch)
  useEffect(() => {
    const initGame = async () => {
      try {
        const [gameResponse, settingsResponse] = await Promise.all([
          fetch(`${BACKEND_URL}/api/game-state`).then(r => r.json()),
          
          // ADDED: .then(r => r.json()) and changed fallback to null
          fetch(`${BACKEND_URL}/api/settings`)
            .then(r => r.json())
            .catch(() => null) 
        ]);

        setGameState(gameResponse);
        setSettings(settingsResponse);

        if (settingsResponse?.env) {
          const model = settingsResponse.env.CLAUDE_CODE_SUBAGENT_MODEL ||
                        settingsResponse.env.ANTHROPIC_DEFAULT_SONNET_MODEL ||
                        'Claude Sonnet 4.6';

          setWhiteProfile(prev => ({ ...prev, model }));
          setBlackProfile(prev => ({ ...prev, model }));
        }
      } catch (error) {
        console.error('Error initializing game:', error);
        setUiStatus({ state: 'error', message: 'Failed to initialize game' });
      }
    };

    initGame();
  }, []);

  // WebSocket connection for real-time updates
  useEffect(() => {
    // WebSocket URL from env var with fallback for local dev
    const wsBaseUrl = process.env.NEXT_PUBLIC_WS_URL || `ws://localhost:8000/ws/game`;

    const wsUrl = `${wsBaseUrl}/ws/game`;

    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('WebSocket connected to backend!');
      setUiStatus({ state: 'idle', message: 'Connected' });
    };

    socket.onmessage = (event: MessageEvent) => {
      const message: WebSocketMessage = JSON.parse(event.data);

      switch (message.type) {
        case 'initial_state':
          setGameState(message.state ?? null);
          break;

        case 'move_complete':
          setGameState(prev => ({
            ...prev!,
            ...message.state
          }));

          // Update win probabilities
          if (message.win_probabilities) {
            setWinProbabilities(message.win_probabilities);
          }

          // Update PV line
          if (message.pv_line && message.pv_line.length > 0) {
            setPvLine(message.pv_line);
          }

          // Update critic commentary
          if (message.critic_commentary) {
            setCriticCommentary(prev => [...prev, message.critic_commentary!]);
          }

          // Only add logs for new moves (deduplication using ref to avoid stale closure)
          const currentMoveCount = message.state?.move_history?.length || 0;
          if (currentMoveCount > lastMoveCountRef.current && message.agent_output) {
            let rawString = '';

            if (typeof message.agent_output === 'string') {
              rawString = message.agent_output;
            } else if (message.agent_output && (message.agent_output as AgentOutput).output) {
              rawString = (message.agent_output as AgentOutput).output;
            }

            if (rawString) {
               const outputLines = String(rawString).split('\n').filter(l => l.trim());
               setMoveLog(prev => [...prev, ...outputLines]);
               setAgentOutput(prev => prev + '\n' + rawString);
            }
            lastMoveCountRef.current = currentMoveCount;
          }

          // Reset UI status after move complete
          setUiStatus({ state: 'idle', message: 'Move complete' });
          break;

        case 'reset':
          setGameState(message.state ?? null);
          setMoveLog([]);
          setAgentOutput('');
          lastMoveCountRef.current = 0;
          setWinProbabilities({ white: 50, black: 50 });
          setCriticCommentary([]);
          setPvLine([]);
          setUiStatus({ state: 'idle', message: 'Game reset' });
          break;

        case 'critic_update':
          // Handle critic analysis update (async broadcast after move)
          if (message.critic_commentary && message.move && message.color) {
            const sentimentEmoji =
              message.critic_commentary.sentiment === 'POSITIVE' ? '✓' :
              message.critic_commentary.sentiment === 'NEGATIVE' ? '⚠' : '→';

            // Update commentary log with move/color correlation
            setCriticCommentary(prev => [...prev, {
              ...message.critic_commentary!,
              move: message.move,
              color: message.color,
              timestamp: message.timestamp || Date.now()
            }]);

            // Append critic lesson to agent output with sentiment emoji and move info
            setAgentOutput(prev => prev +
              `\n[${sentimentEmoji} Critic ${message.critic_commentary!.sentiment}] (${message.color} ${message.move}) ${message.critic_commentary!.lesson}`
            );

            console.log(`Critic analysis for ${message.color} move ${message.move}: ${message.critic_commentary?.sentiment}`);
          }
          break;

        case 'error':
          setUiStatus({ state: 'error', message: message.agent_output ? (typeof message.agent_output === 'string' ? message.agent_output : message.agent_output.error) : 'Unknown error' });
          break;
      }
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
      setUiStatus({ state: 'error', message: 'Connection error' });
    };

    socket.onclose = (event) => {
      console.log(`WebSocket disconnected: ${event.code} ${event.reason}`);
      if (event.code !== 1000) {
        setUiStatus({ state: 'connecting', message: 'Reconnecting...' });
        setTimeout(() => {
          window.location.reload();
        }, 2000);
      }
    };

    return () => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.close(1000, 'Component unmounting');
      }
    };
  }, []);

  // Effect to update UI status based on whose turn it is
  useEffect(() => {
    if (gameState && gameState.status === 'active' && isPlaying && !isPaused) {
      const player = gameState.turn === 'white' ? 'White' : 'Black';
      setUiStatus({
        state: 'thinking',
        message: `Waiting for ${player}'s move...`,
        player: gameState.turn as 'white' | 'black'
      });
    }
  }, [gameState?.turn, isPlaying, isPaused, gameState?.status]);

  // Convert game state board to chess.js format
  const getFenFromBoard = (): string => {
    if (!gameState) return 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

    let fen = '';
    for (let row = 0; row < 8; row++) {
      let emptyCount = 0;
      for (let col = 0; col < 8; col++) {
        const piece = gameState.board[row][col];
        if (piece === '.') {
          emptyCount++;
        } else {
          if (emptyCount > 0) {
            fen += emptyCount.toString();
            emptyCount = 0;
          }
          fen += piece;
        }
      }
      if (emptyCount > 0) {
        fen += emptyCount.toString();
      }
      if (row < 7) fen += '/';
    }

    fen += ' ' + gameState.turn.charAt(0);

    let castlingRights = '';
    if (gameState.castling.white_kingside) castlingRights += 'K';
    if (gameState.castling.white_queenside) castlingRights += 'Q';
    if (gameState.castling.black_kingside) castlingRights += 'k';
    if (gameState.castling.black_queenside) castlingRights += 'q';
    if (castlingRights === '') castlingRights = '-';
    fen += ' ' + castlingRights;

    fen += ' ' + (gameState.en_passant || '-');
    fen += ' ' + gameState.halfmove_clock + ' ' + gameState.fullmove_number;

    return fen;
  };

  // Control functions using /api/control endpoint
  const handleResetGame = async (): Promise<void> => {
    try {
      // Stop the orchestrator first
      await fetch(`${BACKEND_URL}/api/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'stop' })
      });
      // Then reset the board
      await fetch(`${BACKEND_URL}/api/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'reset' })
      });
      setMoveLog([]);
      setAgentOutput('');
      setIsPlaying(false);
      setIsPaused(true);
      setWinProbabilities({ white: 50, black: 50 });
      setCriticCommentary([]);
      setPvLine([]);
      setUiStatus({ state: 'idle', message: 'Game reset' });
    } catch (error) {
      console.error('Error resetting game:', error);
    }
  };

  const handleStartSimulation = async (): Promise<void> => {
    try {
      await fetch(`${BACKEND_URL}/api/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'start' })
      });
      setIsPlaying(true);
      setIsPaused(false);
      setUiStatus({ state: 'analyzing', message: 'Starting analysis...' });
    } catch (error) {
      console.error('Error starting simulation:', error);
    }
  };

  const handlePauseSimulation = async (): Promise<void> => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'pause' })
      });
      const data = await response.json();
      setIsPaused(data.paused);
      setUiStatus({ state: data.paused ? 'idle' : 'analyzing', message: data.paused ? 'Paused' : 'Resumed' });
    } catch (error) {
      console.error('Error toggling pause:', error);
    }
  };

  const handleResetSimulation = async (): Promise<void> => {
    try {
      // Stop the orchestrator
      await fetch(`${BACKEND_URL}/api/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'stop' })
      });
      setIsPlaying(false);
      setIsPaused(true);
      setUiStatus({ state: 'idle', message: 'Simulation stopped' });
    } catch (error) {
      console.error('Error stopping simulation:', error);
    }
  };

  // Helper to format PV line moves
  const formatPvMove = (uciMove: string): string => {
    // Convert UCI to simple algebraic (e.g., e2e4 -> e2-e4)
    if (uciMove.length === 4) {
      return `${uciMove[0]}${uciMove[1]}-${uciMove[2]}${uciMove[3]}`;
    } else if (uciMove.length === 5) {
      // Promotion move
      return `${uciMove[0]}${uciMove[1]}-${uciMove[2]}${uciMove[3]}=${uciMove[4]}`;
    }
    return uciMove;
  };

  // Get sentiment color
  const getSentimentColor = (sentiment: string): string => {
    switch (sentiment) {
      case 'POSITIVE':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'NEGATIVE':
        return 'text-red-600 bg-red-50 border-red-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  // Get status indicator color
  const getStatusColor = (): string => {
    switch (uiStatus.state) {
      case 'thinking':
        return 'bg-yellow-500 animate-pulse';
      case 'analyzing':
        return 'bg-blue-500 animate-pulse';
      case 'connecting':
        return 'bg-orange-500 animate-pulse';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-green-500';
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-indigo-700 text-white p-4 shadow-md">
        <div className="container mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold">Claude Code Chess Arena</h1>
          <div className="flex items-center space-x-4">
            <span data-testid="ws-status" className={`px-3 py-1 rounded-full text-sm flex items-center gap-2 ${
              uiStatus.state === 'error' ? 'bg-red-600' : 'bg-indigo-600'
            }`}>
              <span className={`w-2 h-2 rounded-full ${getStatusColor()}`}></span>
              {uiStatus.message}
            </span>
            <span className="bg-indigo-600 px-3 py-1 rounded-full text-sm">
              {gameState?.turn === 'white' ? 'White to move' : 'Black to move'}
            </span>
          </div>
        </div>
      </header>

      <div className="container mx-auto p-4 flex flex-col lg:flex-row gap-6">
        {/* Chess Board Section */}
        <div className="lg:w-2/3 flex flex-col items-center">
          <div className="bg-white p-6 rounded-xl shadow-lg w-full max-w-2xl">
            <div className="mb-4">
              <Chessboard
                position={getFenFromBoard()}
                boardOrientation="white"
                customBoardStyle={{
                  borderRadius: '8px',
                  boxShadow: '0 5px 15px rgba(0, 0, 0, 0.2)',
                }}
              />
            </div>

            {/* Win Probability Bar */}
            <div data-testid="stockfish-eval" className="mb-4">
              <h3 className="text-sm font-semibold text-gray-600 mb-2">Win Probability</h3>
              <div className="w-full h-6 bg-gray-200 rounded-full overflow-hidden flex">
                <div
                  className="bg-white h-full transition-all duration-500 ease-out"
                  style={{ width: `${winProbabilities.white}%` }}
                  title={`White: ${winProbabilities.white.toFixed(1)}%`}
                >
                  <span className="text-xs font-medium text-gray-800 px-2">
                    {winProbabilities.white >= 10 && `${winProbabilities.white.toFixed(1)}%`}
                  </span>
                </div>
                <div
                  className="bg-gray-800 h-full transition-all duration-500 ease-out flex items-center justify-end"
                  style={{ width: `${winProbabilities.black}%` }}
                  title={`Black: ${winProbabilities.black.toFixed(1)}%`}
                >
                  <span className="text-xs font-medium text-white px-2">
                    {winProbabilities.black >= 10 && `${winProbabilities.black.toFixed(1)}%`}
                  </span>
                </div>
              </div>
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>White: {winProbabilities.white.toFixed(1)}%</span>
                <span>Black: {winProbabilities.black.toFixed(1)}%</span>
              </div>
            </div>

            {/* PV Line Display */}
            {pvLine && pvLine.length > 0 && (
              <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                <h3 className="text-sm font-semibold text-blue-800 mb-2">
                  Stockfish PV Line (Predicted Sequence)
                </h3>
                <div className="flex flex-wrap gap-1">
                  {pvLine.slice(0, 8).map((move, idx) => (
                    <span
                      key={idx}
                      className={`px-2 py-1 rounded text-xs font-mono ${
                        idx % 2 === 0 ? 'bg-white text-gray-800' : 'bg-gray-800 text-white'
                      }`}
                    >
                      {idx % 2 === 0 ? 'W:' : 'B:'} {formatPvMove(move)}
                    </span>
                  ))}
                  {pvLine.length > 8 && (
                    <span className="px-2 py-1 text-xs text-gray-500">
                      +{pvLine.length - 8} more
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Controls */}
            <div className="flex flex-wrap gap-2 justify-center mt-6">
              <button
                data-testid="start-btn"
                onClick={handleStartSimulation}
                disabled={isPlaying && !isPaused}
                className={`px-4 py-2 rounded-lg font-medium ${
                  (isPlaying && !isPaused)
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-green-600 text-white hover:bg-green-700'
                }`}
              >
                Start Simulation
              </button>

              <button
                onClick={handlePauseSimulation}
                disabled={!isPlaying}
                className={`px-4 py-2 rounded-lg font-medium ${
                  !isPlaying
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : isPaused
                      ? 'bg-yellow-500 text-white hover:bg-yellow-600'
                      : 'bg-blue-500 text-white hover:bg-blue-600'
                }`}
              >
                {isPaused ? 'Resume' : 'Pause'}
              </button>

              <button
                onClick={handleResetSimulation}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700"
              >
                Reset Simulation
              </button>

              <button
                onClick={handleResetGame}
                className="px-4 py-2 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700"
              >
                Reset Board
              </button>
            </div>
          </div>
        </div>

        {/* Side Panel */}
        <div className="lg:w-1/3 space-y-6">
          {/* Current Turn Indicator */}
          <div className="bg-white p-4 rounded-xl shadow-lg">
            <h2 className="text-xl font-bold mb-2 text-gray-800">Current Turn</h2>
            <div className={`text-center p-4 rounded-lg ${
              gameState?.turn === 'white'
                ? 'bg-gray-200 text-black'
                : 'bg-gray-800 text-white'
            }`}>
              <span className="text-2xl font-bold capitalize">{gameState?.turn || 'Waiting...'}</span>
            </div>
          </div>

          {/* Agent Profiles */}
          <div className="bg-white p-4 rounded-xl shadow-lg">
            <h2 className="text-xl font-bold mb-4 text-gray-800">Agent Profiles</h2>

            <div className="space-y-4">
              <div className="border border-gray-200 rounded-lg p-3 bg-blue-50">
                <h3 className="font-bold text-blue-800">{whiteProfile.name}</h3>
                <p className="text-sm text-gray-600">Model: {whiteProfile.model}</p>
                <p className="text-xs mt-1 text-gray-700">{whiteProfile.temperament}</p>
              </div>

              <div className="border border-gray-200 rounded-lg p-3 bg-gray-50">
                <h3 className="font-bold text-gray-800">{blackProfile.name}</h3>
                <p className="text-sm text-gray-600">Model: {blackProfile.model}</p>
                <p className="text-xs mt-1 text-gray-700">{blackProfile.temperament}</p>
              </div>
            </div>
          </div>

          {/* Critic Commentary Log */}
          <div className="bg-white p-4 rounded-xl shadow-lg">
            <h2 className="text-xl font-bold mb-2 text-gray-800">Critic Analysis</h2>
            <div data-testid="critic-sentiment" className="overflow-y-auto h-64 border rounded p-2 bg-gray-50 text-sm space-y-2">
              {criticCommentary.length === 0 ? (
                <p className="text-gray-500 italic">No critic analysis yet...</p>
              ) : (
                criticCommentary.map((comment, index) => (
                  <div
                    key={index}
                    className={`p-3 rounded border ${getSentimentColor(comment.sentiment)}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span data-testid="critic-explanation" className="font-semibold text-xs">
                        {comment.sentiment === 'POSITIVE' && '✓ Good'}
                        {comment.sentiment === 'NEGATIVE' && '⚠ Blunder'}
                        {comment.sentiment === 'NEUTRAL' && '→ Neutral'}
                      </span>
                      {comment.color && comment.move && (
                        <span className="text-[10px] font-mono bg-gray-100 px-2 py-0.5 rounded">
                          {comment.color === 'white' ? '♙' : '♟'} {comment.move}
                        </span>
                      )}
                    </div>
                    <p className="text-xs mb-1">{comment.explanation}</p>
                    <p className="text-xs italic opacity-80">💡 {comment.lesson}</p>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Move Log */}
          <div className="bg-white p-4 rounded-xl shadow-lg flex-grow">
            <h2 className="text-xl font-bold mb-2 text-gray-800">Move Log</h2>
            <div data-testid="move-log-white" className="overflow-y-auto h-40 border rounded p-2 bg-gray-50 text-xs">
              {moveLog.length === 0 ? (
                <p className="text-gray-500 italic">No moves recorded yet...</p>
              ) : (
                <div className="space-y-2">
                  {moveLog.map((log, index) => (
                    <div key={index} className="p-2 bg-white rounded border border-gray-200">
                      <pre className="whitespace-pre-wrap">{log}</pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* PGN History */}
          <div className="bg-white p-4 rounded-xl shadow-lg">
            <h2 className="text-xl font-bold mb-2 text-gray-800">PGN History</h2>
            <div className="overflow-y-auto h-32 border rounded p-2 bg-gray-50 text-xs">
              {gameState?.move_history && gameState.move_history.length > 0 ? (
                <div className="grid grid-cols-3 gap-1">
                  {gameState.move_history.map((move, index) => (
                    <div key={index} className="p-1">
                      <span className="font-mono">
                        {move.fullmove}. {move.move} {move.captured ? `(x${move.captured})` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 italic">No moves recorded yet...</p>
              )}
            </div>
          </div>
        </div>

        {/* Chatbot Component - Hidden when game not started */}
        {gameState && <CoachChatbot currentFen={getFenFromBoard()} />}
      </div>
    </div>
  );
};

export default HomePage;
