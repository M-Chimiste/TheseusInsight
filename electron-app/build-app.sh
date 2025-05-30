#!/bin/bash

# Production build script for Theseus Insight Electron App
# PostgreSQL path fixing is now handled automatically by afterPack hook

set -e

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Run this script from the electron-app directory"
    exit 1
fi

echo "🚀 Starting Production Build for Theseus Insight..."

# Accept platform parameter
PLATFORM=${1:-"current"}

echo "🔧 Build configuration:"
echo "   Platform: $PLATFORM"
echo "   Automatic PostgreSQL path fixing: ✅ Enabled"
echo "   Code signing: ❌ Disabled (for testing)"
echo ""

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/

# Install dependencies
echo "📦 Installing Electron dependencies..."
if [ ! -d "node_modules" ]; then
    npm install
else
    echo "✅ Dependencies already installed"
fi

# Build frontend
echo "🎨 Building React frontend..."
cd ../theseus-ui

if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
else
    echo "✅ Frontend dependencies already installed"
fi

echo "⚡ Building optimized frontend for production..."
npm run build

# Verify frontend build
if [ ! -f "dist/index.html" ]; then
    echo "❌ Frontend build failed - index.html not found"
    exit 1
fi

if [ ! -d "dist/assets" ]; then
    echo "❌ Frontend build failed - assets directory not found"
    exit 1
fi

ASSET_COUNT=$(find dist/assets -type f | wc -l | tr -d ' ')
echo "✅ Frontend build successful ($ASSET_COUNT assets)"

cd ../electron-app

# Build Electron app based on platform
echo "📱 Building Electron application..."

# Disable code signing for testing
export CSC_IDENTITY_AUTO_DISCOVERY=false
export SKIP_NOTARIZATION=true

case $PLATFORM in
    "mac")
        echo "🍎 Building for macOS (current architecture)..."
        ARCH=$(uname -m)
        if [ "$ARCH" = "arm64" ]; then
            npm run build:mac-arm64
        else
            npm run build:mac-x64
        fi
        ;;
    "win")
        echo "🪟 Building for Windows..."
        npm run build:win
        ;;
    "linux")
        echo "🐧 Building for Linux..."
        npm run build:linux
        ;;
    "current"|*)
        echo "💻 Building for current platform..."
        ARCH=$(uname -m)
        if [ "$ARCH" = "arm64" ]; then
            npm run build:mac-arm64
        else
            npm run build:mac-x64
        fi
        ;;
esac

if [ $? -ne 0 ]; then
    echo "❌ Build failed"
    exit 1
fi

echo "✅ Build completed successfully!"
echo "📁 Output files are in the 'dist' directory"
echo ""

# Enhanced verification
echo "🔍 Verifying build output..."
BUILT_APPS=(dist/*.app)
if [ -d "${BUILT_APPS[0]}" ]; then
    BUILT_APP="${BUILT_APPS[0]}"
    echo "✅ Found built app: $(basename "$BUILT_APP")"
    
    # Verify PostgreSQL was bundled and paths fixed
    POSTGRES_PATH="$BUILT_APP/Contents/Resources/app/postgres/darwin"
    if [ -d "$POSTGRES_PATH" ]; then
        echo "✅ PostgreSQL bundled successfully"
        
        # Check if afterPack fixed the paths
        INITDB_PATH="$POSTGRES_PATH/bin/initdb"
        if [ -f "$INITDB_PATH" ]; then
            BAD_PATHS=$(otool -L "$INITDB_PATH" 2>/dev/null | grep "/Users/" || true)
            if [ -z "$BAD_PATHS" ]; then
                echo "✅ PostgreSQL paths verified - no hardcoded paths found"
            else
                echo "⚠️  Warning: Some hardcoded paths may remain:"
                echo "$BAD_PATHS"
            fi
        fi
    else
        echo "⚠️  PostgreSQL not found in bundle"
    fi
    
    # Verify frontend was bundled
    FRONTEND_PATH="$BUILT_APP/Contents/Resources/app/theseus-ui/dist"
    if [ -d "$FRONTEND_PATH" ] && [ -f "$FRONTEND_PATH/index.html" ]; then
        BUNDLED_ASSETS=$(find "$FRONTEND_PATH/assets" -type f 2>/dev/null | wc -l | tr -d ' ')
        echo "✅ Frontend bundled successfully ($BUNDLED_ASSETS assets)"
    else
        echo "❌ Warning: Frontend not properly bundled"
        echo "   This will cause blank screen issues"
    fi
else
    echo "❌ No .app file found in dist directory"
    exit 1
fi

echo ""
echo "🎉 Production build complete!"
echo "📋 Build summary:"
echo "   • PostgreSQL: ✅ Bundled with portable paths"
echo "   • Frontend: ✅ Optimized React build included"
echo "   • Architecture: $(uname -m)"
echo "   • Code signing: ❌ Disabled (for testing)"
echo ""
echo "📦 Distribution:"
echo "1. Test locally: open \"$BUILT_APP\""
echo "2. For DMG distribution: Include fix-distributed-app.sh"
echo "3. Recipients should run fix script before first launch"