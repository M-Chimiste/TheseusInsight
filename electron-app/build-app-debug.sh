#!/bin/bash

# Debug build script for Theseus Insight Electron App
# Builds a macOS DMG without code signing for local testing.

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

# Bundle a standalone Python runtime with dependencies
echo "🐍 Bundling Python runtime..."
if [ -f "./bundle-python-runtime.sh" ]; then
    ./bundle-python-runtime.sh
else
    echo "⚠️  bundle-python-runtime.sh not found, skipping runtime bundling"
    echo "   The app will require a system Python installation"
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

npm run lint >/dev/null 2>&1 || true
# Build the Electron app
echo "📱 Building Electron app for $BUILD_ARCH..."
npm run build:mac-$BUILD_ARCH

if [ $? -ne 0 ]; then
    echo "❌ Electron build failed"
    exit 1
fi

echo "✅ Build completed successfully!"
echo "📁 Output files are in the 'dist' directory"
echo ""


# Verify build output
echo "🔍 Verifying build output..."
BUILT_APP=$(find dist -name "*.app" -type d | head -1)

if [ -z "$BUILT_APP" ]; then
    echo "❌ No .app file found in dist directory"
    exit 1
fi

echo "✅ Found built app: $(basename "$BUILT_APP")"

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