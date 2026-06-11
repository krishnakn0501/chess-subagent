@echo off
REM build-frontend.bat

echo Building Claude Code Chess Arena Frontend

REM Install dependencies if not already installed
echo Installing dependencies...
npm install

REM Build the Next.js application
echo Building Next.js application...
npm run build

echo Frontend build complete!
echo To serve the static site, run: python app.py