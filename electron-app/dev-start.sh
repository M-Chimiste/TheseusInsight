#!/bin/bash

# Development startup script for Theseus Insight Electron App
echo "Starting Theseus Insight in development mode..."

# Check if we're in the electron-app directory
if [ ! -f "package.json" ]; then
    echo "Error: Run this script from the electron-app directory"
    exit 1
fi

# Function to cleanup background processes
cleanup() {
    echo "Shutting down development servers..."
    kill $VITE_PID 2>/dev/null
    exit 0
}

# Set up trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Start Vite dev server in the background
echo "Starting Vite development server..."
cd ../theseus-ui
npm run dev &
VITE_PID=$!

# Wait a moment for Vite to start
sleep 3

# Return to electron-app directory and start Electron in development mode
cd ../electron-app
echo "Starting Electron app in development mode..."
echo "Note: Make sure your FastAPI backend is running on port 8000"
echo "UI changes will now be reflected immediately in the Electron app!"

NODE_ENV=development electron .

# Keep script running until user stops it
wait