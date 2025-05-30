#!/bin/bash

# Simple build script for Theseus Insight - Better Distribution
set -e

echo "🔧 Building Robust Theseus Insight App..."

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Run this script from the electron-app directory"
    exit 1
fi

# Step 1: Build the UI
echo "🎨 Building React UI..."
cd ../theseus-ui

if [ ! -d "node_modules" ]; then
    echo "📦 Installing UI dependencies..."
    npm install
fi

echo "🔨 Building UI for production..."
npm run build

if [ ! -d "dist" ]; then
    echo "❌ Error: UI build failed"
    exit 1
fi

echo "✅ UI build completed"

# Step 2: Switch to robust main.js
echo "⚡ Switching to robust main.js..."
cd ../electron-app

# Backup original main.js if it exists
if [ -f "main.js" ] && [ ! -f "main.js.backup" ]; then
    cp main.js main.js.backup
    echo "📋 Backed up original main.js"
fi

# Copy robust version
cp main-robust.js main.js
echo "✅ Using robust main.js"

# Step 3: Clean and install dependencies
echo "📦 Installing Electron dependencies..."
if [ ! -d "node_modules" ]; then
    npm install
fi

# Step 4: Build simplified version (no database, minimal dependencies)
echo "⚡ Building simplified Electron application..."

# Detect current architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    BUILD_ARCH="arm64"
    echo "🍎 Building for Apple Silicon (arm64)"
elif [ "$ARCH" = "x86_64" ]; then
    BUILD_ARCH="x64"
    echo "💻 Building for Intel (x64)"
else
    BUILD_ARCH="x64"
    echo "❓ Unknown architecture, defaulting to x64"
fi

# Disable code signing for simple build
export CSC_IDENTITY_AUTO_DISCOVERY=false
export SKIP_NOTARIZATION=true

# Build for current architecture
if [ "$BUILD_ARCH" = "arm64" ]; then
    npm run build:mac-arm64
else
    npm run build:mac-x64
fi

echo "🎉 Simple build completed!"
echo "📁 Output files are in the 'dist' directory"
echo ""
echo "🚨 Important: This is a simplified build"
echo "   • Uses system Python instead of bundled Python"
echo "   • Requires Python and pip packages on target machine"
echo "   • Provides better error messages to users"
echo "   • More compatible across different Macs"
echo ""

# Restore original main.js
if [ -f "main.js.backup" ]; then
    mv main.js.backup main.js
    echo "♻️  Restored original main.js"
fi

if [ -d "dist" ]; then
    echo "📋 Built files:"
    ls -la dist/ | grep -E "\.(dmg|app)$"
fi

echo ""
echo "📧 To test this version:"
echo "   1. Install the DMG on the target Mac"
echo "   2. If it fails, run the debug-app.sh script"
echo "   3. Install any missing dependencies it reports" 