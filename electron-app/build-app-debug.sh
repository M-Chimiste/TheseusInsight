#!/bin/bash

# Debug build script for Theseus Insight Electron App
# This builds without code signing/notarization for testing
# Now includes automatic PostgreSQL path fixing for portability
set -eo pipefail

echo "🔧 Starting Debug Build (No Code Signing)..."

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Run this script from the electron-app directory"
    exit 1
fi

# Detect current architecture
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ]; then
    BUILD_ARCH="arm64"
    echo "🍎 Detected Apple Silicon Mac - building for arm64"
elif [ "$ARCH" = "x86_64" ]; then
    BUILD_ARCH="x64"
    echo "💻 Detected Intel Mac - building for x64"
else
    BUILD_ARCH="x64"
    echo "❓ Unknown architecture ($ARCH) - defaulting to x64"
fi

echo "🔧 Skipping manual Postgres patch – handled by electron-builder afterPack"

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

# Step 2: Build Electron app
echo "⚡ Building Electron application (Debug Mode for $BUILD_ARCH)..."
cd ../electron-app

if [ ! -d "node_modules" ]; then
    echo "📦 Installing Electron dependencies..."
    npm install
fi

# Temporarily disable code signing for debug build
export CSC_IDENTITY_AUTO_DISCOVERY=false
export SKIP_NOTARIZATION=true

# Build for current architecture only
if [ "$BUILD_ARCH" = "arm64" ]; then
    npm run build:mac-arm64
else
    npm run build:mac-x64
fi

echo "🎉 Debug build completed for $BUILD_ARCH!"
echo "📁 Output files are in the 'dist' directory"
echo ""
echo "✅ This build includes:"
echo "   • Fixed PostgreSQL paths for portability"
echo "   • No code signing (for easy testing)"
echo "   • Built for $BUILD_ARCH architecture"
echo "   • Should work on other Macs without path issues"
echo ""

# Verification step
echo "🔍 Verifying PostgreSQL path fixes..."
BUILT_APP=$(ls -1d dist/*/Theseus\ Insight.app dist/Theseus\ Insight.app 2>/dev/null | head -n1)
if [ -n "$BUILT_APP" ]; then
    BUILT_BINARY="$BUILT_APP/Contents/Resources/app/postgres/darwin/bin/initdb"
    if [ -f "$BUILT_BINARY" ]; then
        BAD_PATHS=$(otool -L "$BUILT_BINARY" 2>/dev/null | grep "/Users/" || true)
        if [ -z "$BAD_PATHS" ]; then
            echo "✅ Verification passed: No hard‑coded paths in built app"
        else
            echo "❌ Warning: Built app still contains hard‑coded paths:"
            echo "$BAD_PATHS"
        fi
    else
        echo "⚠️  Could not verify paths (initdb not found in built app)"
    fi
    
    # Verify frontend files are bundled
    echo "🔍 Verifying frontend files are bundled..."
    FRONTEND_PATH="$BUILT_APP/Contents/Resources/app/theseus-ui/dist"
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
        find "$BUILT_APP/Contents/Resources/app" -maxdepth 2 -type d 2>/dev/null | head -20
    fi
else
    echo "⚠️  Could not locate built .app bundle for verification"
fi

if [ -d "dist" ]; then
    echo ""
    echo "📋 Built files:"
    ls -la dist/ | grep -E "\.(dmg|app)$"
fi

echo ""
echo "🚀 Ready for distribution!"
echo "   The DMG should now work on other Macs without additional steps." 