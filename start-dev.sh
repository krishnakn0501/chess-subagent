#!/bin/bash
# start-dev.sh

echo "Starting Claude Code Chess Arena Development Environment"

# Start FastAPI backend in background
echo "Starting FastAPI backend..."
uvicorn app:app --reload --port 8000 &
FASTAPI_PID=$!

# Wait a moment for FastAPI to start
sleep 3

# Start Next.js frontend
echo "Starting Next.js frontend..."
npm run dev

# Cleanup on exit
trap "kill $FASTAPI_PID" EXIT