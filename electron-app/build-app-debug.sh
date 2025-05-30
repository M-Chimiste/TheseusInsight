#!/bin/bash

# Debug build script for Theseus Insight Electron App
# This builds without code signing/notarization for testing
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

# Step 2: Build Electron app without signing
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
echo "🚨 Important: This is a debug build without code signing"
echo "   • Safe for local testing and development"
echo "   • Built for $BUILD_ARCH architecture"
echo "   • May require 'Open Anyway' in Security & Privacy on other Macs"
echo "   • For distribution, use the regular build-app.sh script with proper signing"

if [ -d "dist" ]; then
    echo ""
    echo "📋 Built files:"
    ls -la dist/
fi 