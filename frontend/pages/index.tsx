// pages/index.tsx
import React, { useState, useEffect } from 'react';
import { Chessboard } from 'react-chessboard';

// Type definitions for WebSocket messages
type AgentOutput = {
  success: boolean;
  output: string;
  error: string;
};

type WebSocketMessage = {
  type: 'initial_state' | 'move_complete' | 'reset';
  state: GameState;
  agent_output: AgentOutput | string | null; // Safely handle objects or strings
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

const HomePage: React.FC = () => {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(true);
  const [moveLog, setMoveLog] = useState<string[]>([]);
  const [agentOutput, setAgentOutput] = useState<string>('');
  const [lastMoveCount, setLastMoveCount] = useState<number>(0);
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

  // Base URL for the FastAPI Backend
  const BACKEND_URL = 'http://localhost:8000';

  // Initialize game state on load (initial fetch)
  useEffect(() => {
    const initGame = async () => {
      try {
        const [gameResponse, settingsResponse] = await Promise.all([
          fetch(`${BACKEND_URL}/api/game-state`).then(r => r.json()),
          fetch(`${BACKEND_URL}/api/settings`).catch(() => ({}))
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
      }
    };

    initGame();
  }, []);

  // WebSocket connection for real-time updates
  useEffect(() => {
    // Point directly to the FastAPI server port
    const wsUrl = 'ws://localhost:8000/ws/game';

    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('WebSocket connected to backend!');
    };

    socket.onmessage = (event: MessageEvent) => {
      const message: WebSocketMessage = JSON.parse(event.data);

      switch (message.type) {
        case 'initial_state':
          setGameState(message.state);
          break;

        case 'move_complete':
          setGameState(prev => ({
            ...prev!,
            ...message.state
          }));

          // Only add logs for new moves (deduplication)
          const currentMoveCount = message.state.move_history?.length || 0;
          if (currentMoveCount > lastMoveCount && message.agent_output) {
            let rawString = '';

            if (typeof message.agent_output === 'string') {
              rawString = message.agent_output;
            } else if (message.agent_output.output) {
              rawString = message.agent_output.output;
            }

            if (rawString) {
               const outputLines = String(rawString).split('\n').filter(l => l.trim());
               setMoveLog(prev => [...prev, ...outputLines]);
               setAgentOutput(prev => prev + '\n' + rawString);
            }
            setLastMoveCount(currentMoveCount);
          }
          break;

        case 'reset':
          setGameState(message.state);
          setMoveLog([]);
          setAgentOutput('');
          setLastMoveCount(0);
          break;
      }
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    socket.onclose = (event) => {
      console.log(`WebSocket disconnected: ${event.code} ${event.reason}`);
      if (event.code !== 1000) {
        console.log('Attempting to reconnect in 2 seconds...');
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
    } catch (error) {
      console.error('Error stopping simulation:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-indigo-700 text-white p-4 shadow-md">
        <div className="container mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold">Claude Code Chess Arena</h1>
          <div className="flex items-center space-x-4">
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

            {/* Controls */}
            <div className="flex flex-wrap gap-2 justify-center mt-6">
              <button
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

          {/* Move Log */}
          <div className="bg-white p-4 rounded-xl shadow-lg flex-grow h-64">
            <h2 className="text-xl font-bold mb-2 text-gray-800">Move Log</h2>
            <div className="overflow-y-auto h-48 border rounded p-2 bg-gray-50 text-xs">
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
            <div className="overflow-y-auto h-40 border rounded p-2 bg-gray-50 text-xs">
              {gameState?.move_history && gameState.move_history.length > 0 ? (
                <div className="grid grid-cols-3 gap-1">
                  {gameState.move_history.map((move, index) => (
                    <div key={index} className="p-1">
                      <span className="font-mono">
                        {move.fullmove}. {move.move} {move.captured ? `(captures ${move.captured})` : ''}
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
      </div>
    </div>
  );
};

export default HomePage;