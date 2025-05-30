#!/bin/bash

# Comprehensive build script for Theseus Insight Electron App
set -e  # Exit on any error

echo "🚀 Starting Theseus Insight Electron App Build Process..."

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Run this script from the electron-app directory"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command_exists npm; then
    echo "❌ Error: npm is not installed"
    exit 1
fi

if ! command_exists node; then
    echo "❌ Error: Node.js is not installed"
    exit 1
fi

echo "✅ Prerequisites check passed"

# Step 1: Build the UI
echo "🎨 Building React UI..."
cd ../theseus-ui

if [ ! -f "package.json" ]; then
    echo "❌ Error: theseus-ui directory not found or invalid"
    exit 1
fi

# Install UI dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing UI dependencies..."
    npm install
fi

# Build the UI
echo "🔨 Building UI for production..."
npm run build

# Check if build was successful
if [ ! -d "dist" ]; then
    echo "❌ Error: UI build failed - dist directory not found"
    exit 1
fi

echo "✅ UI build completed successfully"

# Step 2: Verify config files
echo "📋 Verifying configuration files..."
cd ../

CONFIG_FILES=("config/orchestration.json" "config/research_interests.txt" "config/arxiv_taxonomy.json")
for file in "${CONFIG_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "⚠️  Warning: Config file $file not found"
    else
        echo "✅ Found: $file"
    fi
done

# Step 3: Build Electron app
echo "⚡ Building Electron application..."
cd electron-app

# Install Electron dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Electron dependencies..."
    npm install
fi

# Determine build target
BUILD_TARGET=""
case "$1" in
    "mac"|"darwin")
        BUILD_TARGET="build:mac"
        echo "🍎 Building for macOS..."
        ;;
    "win"|"windows")
        BUILD_TARGET="build:win"
        echo "🪟 Building for Windows..."
        ;;
    "linux")
        BUILD_TARGET="build:linux"
        echo "🐧 Building for Linux..."
        ;;
    "")
        BUILD_TARGET="build"
        echo "🔧 Building for current platform..."
        ;;
    *)
        echo "❌ Error: Unknown build target '$1'"
        echo "Usage: $0 [mac|win|linux]"
        exit 1
        ;;
esac

# Run the build
npm run $BUILD_TARGET

# Check if build was successful
if [ $? -eq 0 ]; then
    echo "🎉 Build completed successfully!"
    echo "📁 Output files are in the 'dist' directory"
    
    # List the output files
    if [ -d "dist" ]; then
        echo "📋 Built files:"
        ls -la dist/
    fi
    
    echo ""
    echo "🚀 Your Theseus Insight Electron app is ready!"
    echo "💡 The built app includes:"
    echo "   • React UI (from theseus-ui/dist)"
    echo "   • Python backend (FastAPI)"
    echo "   • Configuration files"
    echo "   • Default environment template"
    echo "   • Embedded PostgreSQL"
else
    echo "❌ Build failed!"
    exit 1
fi 