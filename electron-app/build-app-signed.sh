#!/bin/bash

# Turnkey signed build script for Theseus Insight Electron App
# Builds a macOS DMG with full Python runtime and code signing for distribution.
# Creates a completely self-contained app that requires no Python installation.

set -e

echo "🔐 Starting Turnkey Signed Build (Full Python Runtime + Code Signing)..."

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Run this script from the electron-app directory"
    exit 1
fi

# Check for required certificates
echo "🔍 Checking for code signing certificates..."
CERT_COUNT=$(security find-identity -v -p codesigning | grep "Developer ID Application" | wc -l | tr -d ' ')
if [ "$CERT_COUNT" -eq "0" ]; then
    echo "❌ Error: No Developer ID Application certificates found"
    echo "   Please install your Apple Developer certificates first"
    echo "   Run: security find-identity -v -p codesigning"
    exit 1
fi

echo "✅ Found $CERT_COUNT Developer ID Application certificate(s)"

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

# Bundle complete Python runtime with dependencies
echo "🐍 Bundling complete Python runtime..."
if [ -f "./bundle-python-runtime.sh" ]; then
    ./bundle-python-runtime.sh
    if [ ! -d "python_runtime" ]; then
        echo "❌ Python runtime bundling failed"
        exit 1
    fi
    echo "✅ Python runtime bundled successfully"
else
    echo "❌ bundle-python-runtime.sh not found"
    echo "   This script is required for a turnkey DMG"
    exit 1
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

# Lint check (optional, don't fail build)
npm run lint >/dev/null 2>&1 || true

# Build the Electron app with signing
echo "📱 Building and signing Electron app for $BUILD_ARCH..."
echo "⏱️  This may take 3-5 minutes due to Python runtime signing..."
npm run build:mac-$BUILD_ARCH

if [ $? -ne 0 ]; then
    echo "❌ Electron build/signing failed"
    exit 1
fi

echo "✅ Build and signing completed successfully!"
echo "📁 Output files are in the 'dist' directory"
echo ""

# Verify build output and signing
echo "🔍 Verifying build output and code signature..."
BUILT_APP=$(find dist -name "*.app" -type d | head -1)

if [ -z "$BUILT_APP" ]; then
    echo "❌ No .app file found in dist directory"
    exit 1
fi

echo "✅ Found built app: $(basename "$BUILT_APP")"

# Verify code signature
echo "🔐 Verifying code signature..."
codesign --verify --verbose "$BUILT_APP"
if [ $? -eq 0 ]; then
    echo "✅ Code signature verification passed"
    
    # Show signature details
    echo "📋 Signature details:"
    codesign -dvvv "$BUILT_APP" 2>&1 | grep -E "(Authority|TeamIdentifier|Identifier|Format)"
else
    echo "❌ Code signature verification failed"
    exit 1
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

# Check if we should notarize
# Verify Python runtime was bundled
PYTHON_RUNTIME_PATH="$BUILT_APP/Contents/Resources/app/python_runtime"
if [ -d "$PYTHON_RUNTIME_PATH" ]; then
    RUNTIME_SIZE=$(du -sh "$PYTHON_RUNTIME_PATH" | cut -f1)
    echo "✅ Python runtime bundled ($RUNTIME_SIZE)"
else
    echo "❌ Warning: Python runtime not found in app bundle"
fi

echo ""
echo "📋 Next steps for distribution:"
echo "1. Test the signed app locally: open \"$BUILT_APP\""
echo "2. 🎯 This is a TURNKEY DMG - no Python installation required"
echo "3. For public distribution, consider notarization:"
echo "   xcrun notarytool submit dist/*.dmg --keychain-profile \"AC_PASSWORD\""
echo "4. After notarization: xcrun stapler staple dist/*.dmg"
echo ""
echo "🎉 Turnkey signed build complete!" 