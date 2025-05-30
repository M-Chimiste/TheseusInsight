#!/bin/bash

# Debug build script for Theseus Insight Electron App
# This builds without code signing/notarization for testing
# PostgreSQL path fixing is now handled automatically by afterPack hook

set -e

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

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/
rm -rf node_modules/.cache/

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Bundle Python dependencies
echo "🐍 Bundling Python dependencies..."
if [ -f "./bundle-python-deps.sh" ]; then
    if ./bundle-python-deps.sh; then
        echo "✅ Python dependencies bundled successfully"
    else
        echo "❌ Failed to bundle Python dependencies"
        echo "   The app may not work on systems without Python packages"
        echo "   Continuing with build anyway..."
    fi
else
    echo "⚠️  bundle-python-deps.sh not found, skipping dependency bundling"
    echo "   Recipients will need to install Python packages manually"
fi

# Build the React frontend
echo "🏗️  Building React UI..."
cd ../theseus-ui

if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

echo "⚡ Building optimized frontend..."
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

# Build the Electron app with automatic PostgreSQL path fixing
echo "📱 Building Electron app for $BUILD_ARCH..."
echo "🔧 Note: PostgreSQL path fixing will run automatically via afterPack hook"
npm run build:mac-$BUILD_ARCH

if [ $? -ne 0 ]; then
    echo "❌ Electron build failed"
    exit 1
fi

echo "✅ Build completed successfully!"
echo "📁 Output files are in the 'dist' directory"
echo ""

# Enhanced verification
echo "🔍 Verifying build output..."
BUILT_APP=$(find dist -name "*.app" -type d | head -1)

if [ -z "$BUILT_APP" ]; then
    echo "❌ No .app file found in dist directory"
    exit 1
fi

echo "✅ Found built app: $(basename "$BUILT_APP")"

# Verify PostgreSQL was bundled
POSTGRES_PATH="$BUILT_APP/Contents/Resources/app/postgres/darwin"
if [ -d "$POSTGRES_PATH" ]; then
    echo "✅ PostgreSQL bundled successfully"
    
    # Enhanced verification - check multiple binaries
    echo "🔍 Detailed PostgreSQL path verification..."
    INITDB_PATH="$POSTGRES_PATH/bin/initdb"
    POSTGRES_BIN_PATH="$POSTGRES_PATH/bin/postgres"
    
    if [ -f "$INITDB_PATH" ]; then
        echo "🔍 Checking initdb dependencies:"
        otool -L "$INITDB_PATH" | while read -r line; do
            line=$(echo "$line" | xargs)  # trim whitespace
            if [[ "$line" == *"/Users/"* ]] || [[ "$line" == *"TheseusInsight"* ]]; then
                echo "  ❌ HARDCODED: $line"
            elif [[ "$line" == *"postgres"* ]] && [[ "$line" == "/"* ]] && [[ "$line" != "/@"* ]]; then
                echo "  ❌ ABSOLUTE: $line"
            elif [[ "$line" == *".dylib"* ]]; then
                echo "  ✅ OK: $line"
            fi
        done
        
        # Quick check for any remaining bad paths
        BAD_PATHS=$(otool -L "$INITDB_PATH" 2>/dev/null | grep -E "(/Users/|TheseusInsight)" || true)
        if [ -z "$BAD_PATHS" ]; then
            echo "✅ initdb: No hardcoded paths found"
        else
            echo "❌ initdb: Some hardcoded paths remain:"
            echo "$BAD_PATHS" | sed 's/^/    /'
        fi
    fi
    
    if [ -f "$POSTGRES_BIN_PATH" ]; then
        BAD_PATHS=$(otool -L "$POSTGRES_BIN_PATH" 2>/dev/null | grep -E "(/Users/|TheseusInsight)" || true)
        if [ -z "$BAD_PATHS" ]; then
            echo "✅ postgres: No hardcoded paths found"
        else
            echo "❌ postgres: Some hardcoded paths remain:"
            echo "$BAD_PATHS" | sed 's/^/    /'
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

echo ""
echo "🎉 Debug build complete!"
echo "📋 Next steps:"
echo "1. Test the app locally: open \"$BUILT_APP\""
echo "2. If distributing: Include fix-distributed-app.sh with the DMG"
echo "3. Recipients should run the fix script before first launch" 