#!/bin/bash

# Ultra-minimal signed build script for Theseus Insight Electron App
# Completely excludes Python runtime for fastest signing

set -e

echo "🔐 Starting Ultra-Minimal Signed Build (No Python Bundle)..."

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

# Remove any existing python_runtime directory to ensure it's not bundled
echo "🗑️  Removing Python runtime to avoid signing delays..."
rm -rf python_runtime/

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
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

# Temporarily modify package.json to exclude Python runtime from extraResources
echo "⚙️  Temporarily modifying build config for ultra-minimal build..."
cp package.json package.json.bak

# Create a minimal package.json for this build
cat > package.json.minimal << 'EOF'
{
  "name": "theseus-desktop",
  "version": "0.9.4",
  "main": "main.js",
  "description": "Electron wrapper for Theseus Insight",
  "author": "Theseus Insight Team",
  "scripts": {
    "build:mac-arm64": "electron-builder --mac --arm64",
    "build:mac-x64": "electron-builder --mac --x64"
  },
  "build": {
    "appId": "com.theseusinsight.desktop",
    "productName": "Theseus Insight",
    "directories": {
      "output": "dist"
    },
    "asar": true,
    "asarUnpack": [
      "**/theseus_insight/**/*",
      "**/run_theseus_insight.py",
      "**/requirements.txt"
    ],
    "files": [
      "**/*",
      "!node_modules/*/{CHANGELOG.md,README.md,readme.md,example,examples,**/test/**}",
      "!unused",
      "!python_runtime/**"
    ],
    "extraResources": [
      {
        "from": "../",
        "to": "app",
        "filter": [
          "theseus_insight/**",
          "theseus-ui/dist/**",
          "config/**",
          "data/**",
          "run_theseus_insight.py",
          "requirements.txt"
        ]
      },
      {
        "from": "env.template",
        "to": ".env"
      }
    ],
    "mac": {
      "icon": "icons/mac/icon.icns",
      "hardenedRuntime": true,
      "gatekeeperAssess": false,
      "entitlements": "build/entitlements.mac.plist",
      "entitlementsInherit": "build/entitlements.mac.inherit.plist",
      "category": "public.app-category.productivity",
      "identity": "Christian Merrill (4H8Z97B24M)",
      "target": [
        {
          "target": "dmg",
          "arch": ["x64", "arm64"]
        }
      ]
    }
  },
  "engines": {
    "node": ">=20"
  },
  "devDependencies": {
    "@electron/notarize": "^2.5.0",
    "electron": "^31.0.0",
    "electron-builder": "^24.11.0"
  }
}
EOF

# Use the minimal config
mv package.json.minimal package.json

# Build the Electron app with signing (should be MUCH faster now)
echo "📱 Building and signing Electron app for $BUILD_ARCH..."
echo "⚠️  This build requires system Python with packages installed"
echo "⏱️  Should complete in under 2 minutes..."

START_TIME=$(date +%s)
npm run build:mac-$BUILD_ARCH

if [ $? -ne 0 ]; then
    echo "❌ Electron build/signing failed"
    # Restore original package.json
    mv package.json.bak package.json
    exit 1
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
echo "✅ Build and signing completed in ${DURATION} seconds!"

# Restore original package.json
mv package.json.bak package.json

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
fi

echo ""
echo "📋 Next steps for distribution:"
echo "1. Test the signed app locally: open \"$BUILT_APP\""
echo "2. ⚠️  Recipients need Python 3.11+ with: pip install -r requirements.txt"
echo "3. For notarization: xcrun notarytool submit dist/*.dmg --keychain-profile \"AC_PASSWORD\""
echo "4. After notarization: xcrun stapler staple dist/*.dmg"
echo ""
echo "🎉 Ultra-minimal signed build complete in ${DURATION} seconds!" 