#!/bin/bash
# build-frontend.sh

echo "Building Claude Code Chess Arena Frontend"

# Install dependencies if not already installed
echo "Installing dependencies..."
npm install

# Build the Next.js application
echo "Building Next.js application..."
npm run build

# Export as static site
echo "Exporting as static site..."
npm run build

echo "Frontend build complete!"
echo "To serve the static site, run: python app.py"