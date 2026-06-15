/**
 * api/evaluate.js - Serverless Vercel endpoint for Stockfish evaluation
 * Deployed as its own Vercel project (Engine microservice).
 *
 * Accepts POST request with { fen: string, depth: number }
 * Returns { best_move: string, cp: number }
 *
 * CORS: Configured to accept cross-origin POST requests from any origin.
 */

const stockfish = require('stockfish');

module.exports = async function handler(req, res) {
  // ── CORS headers (explicit, every response) ──────────────────────────
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  // Handle preflight OPTIONS request
  if (req.method === 'OPTIONS') {
    return res.status(204).end();
  }

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

    // 8 seconds max to respect Vercel limits
    const timeout = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        res.status(504).json({ error: 'Engine timeout' });
        resolve();
      }
    }, 8000);

    engine.onmessage = (line) => {
      if (resolved || typeof line !== 'string') return;

      // Extract Evaluation Score (Centipawns)
      if (line.includes('info depth') && line.includes('score cp')) {
        const match = line.match(/score cp (-?\d+)/);
        if (match) {
          cp = parseInt(match[1], 10);
        }
      }

      // Extract Mate Evaluation
      if (line.includes('score mate')) {
        const mateMatch = line.match(/score mate (-?\d+)/);
        if (mateMatch) {
          const mateIn = parseInt(mateMatch[1], 10);
          cp = mateIn > 0 ? 10000 : -10000;
        }
      }

      // Detect Best Move and return response
      if (line.startsWith('bestmove')) {
        const parts = line.split(' ');
        bestMove = parts[1];

        clearTimeout(timeout);
        resolved = true;

        res.status(200).json({ best_move: bestMove, cp: cp !== null ? cp : 0 });
        resolve();
      }
    };

    // Initialize and kick off evaluation
    engine.postMessage('uci');
    engine.postMessage(`position fen ${fen}`);
    engine.postMessage(`go depth ${safeDepth}`);
  });
};
