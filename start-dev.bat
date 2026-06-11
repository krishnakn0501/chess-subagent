@echo off
REM start-dev.bat

echo Starting Claude Code Chess Arena Development Environment

REM Start FastAPI backend in background
echo Starting FastAPI backend...
start "FastAPI Server" cmd /k "uvicorn app:app --reload --port 8000"

REM Wait a moment for FastAPI to start
timeout /t 3 /nobreak >nul

REM Start Next.js frontend
echo Starting Next.js frontend...
npm run dev