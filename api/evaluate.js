/**
 * api/evaluate.js - Serverless Vercel endpoint for Stockfish evaluation
 * Accepts POST request with { fen: string, depth: number }
 * Returns { best_move: string, cp: number }
 */

const stockfish = require('stockfish');

module.exports = async function handler(req, res) {
  // Allow only POST requests
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { fen, depth } = req.body;

  if (!fen || typeof fen !== 'string') {
    return res.status(400).json({ error: 'Missing or invalid "fen" field' });
  }

  const safeDepth = typeof depth === 'number' && depth > 0 ? depth : 15;

  return new Promise((resolve) => {
    const engine = stockfish();
    let bestMove = null;
    let cp = null;
    let resolved = false;

    const timeout = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        engine.terminate();
        res.status(504).json({ error: 'Engine timeout' });
        resolve();
      }
    }, 8000); // 8 seconds max to respect Vercel limits

    engine.onmessage = (line) => {
      const str = line.toString();

      if (str.startsWith('bestmove')) {
        const parts = str.split(' ');
        bestMove = parts[1];
      }

      if (str.includes('info depth') && str.includes('score cp')) {
        const match = str.match(/score cp (-?\d+)/);
        if (match) {
          cp = parseInt(match[1], 10);
        }
      }

      if (str.includes('score mate')) {
        const mateMatch = str.match(/score mate (-?\d+)/);
        if (mateMatch) {
          const mateIn = parseInt(mateMatch[1], 10);
          // Convert mate to centipawn equivalent for consistency
          cp = mateIn > 0 ? 10000 : -10000;
        }
      }

      if (str.startsWith('bestmove') && !resolved) {
        clearTimeout(timeout);
        resolved = true;
        engine.terminate();
        res.status(200).json({ best_move: bestMove, cp: cp !== null ? cp : 0 });
        resolve();
      }
    };

    engine.postMessage('uci');
    engine.postMessage(`position fen ${fen}`);
    engine.postMessage(`go depth ${safeDepth}`);
  });
};