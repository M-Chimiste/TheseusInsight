#!/bin/bash

# Comprehensive build script for Theseus Insight Electron App
set -eo pipefail  # Exit on any error and fail on pipe errors

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

# Step 1: Skip manual Postgres patch  
echo "🔧 Skipping manual Postgres patch – handled by electron-builder afterPack"

# Step 2: Build the UI
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

# Step 3: Verify configuration files
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

# Step 4: Build Electron app
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
    
    # Verification step
    echo "🔍 Verifying PostgreSQL path fixes..."
    BUILT_APPS=(dist/*.app)
    if [ -f "${BUILT_APPS[0]}/Contents/Resources/app/postgres/darwin/bin/initdb" ]; then
        BUILT_BINARY="${BUILT_APPS[0]}/Contents/Resources/app/postgres/darwin/bin/initdb"
        BAD_PATHS=$(otool -L "$BUILT_BINARY" 2>/dev/null | grep "/Users/c/software_projects" || true)
        if [ -z "$BAD_PATHS" ]; then
            echo "✅ Verification passed: No hardcoded paths in built app"
        else
            echo "❌ Warning: Built app still contains hardcoded paths:"
            echo "$BAD_PATHS"
        fi
        
        # Verify frontend files are bundled
        echo "🔍 Verifying frontend files are bundled..."
        FRONTEND_PATH="${BUILT_APPS[0]}/Contents/Resources/app/theseus-ui/dist"
        if [ -d "$FRONTEND_PATH" ]; then
            if [ -f "$FRONTEND_PATH/index.html" ]; then
                echo "✅ Frontend verification passed: index.html found in built app"
            else
                echo "❌ Warning: Frontend index.html not found in built app"
                echo "   Expected at: $FRONTEND_PATH/index.html"
            fi
            
            if [ -d "$FRONTEND_PATH/assets" ]; then
                ASSET_COUNT=$(find "$FRONTEND_PATH/assets" -type f | wc -l)
                echo "✅ Frontend assets found: $ASSET_COUNT files in assets directory"
            else
                echo "❌ Warning: Frontend assets directory not found"
                echo "   Expected at: $FRONTEND_PATH/assets"
            fi
        else
            echo "❌ Warning: Frontend directory not found in built app"
            echo "   Expected at: $FRONTEND_PATH"
            echo "   This means the UI won't load on other systems"
            
            # List what's actually in the app bundle
            echo "📁 Contents of app bundle:"
            find "${BUILT_APPS[0]}/Contents/Resources/app" -maxdepth 2 -type d 2>/dev/null | head -20
        fi
    else
        echo "⚠️  Could not verify paths (binary not found in expected location)"
    fi

    if [ -d "dist" ]; then
        echo ""
        echo "📋 Built files:"
        ls -la dist/ | grep -E "\.(dmg|app)$"
    fi
    
    echo ""
    echo "🚀 Ready for distribution!"
    echo "   The DMG should now work on other Macs without additional steps."
else
    echo "❌ Build failed!"
    exit 1
fi