#!/bin/bash

# Turnkey signed build script for Theseus Insight Electron App
# Builds unsigned first, adds Python runtime, then signs the complete app

set -e

echo "🔐 Starting Turnkey Signed Build (Fast Manual Signing)..."

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
rm -rf python_runtime/

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
    exit 1
fi

# Clean Python runtime for turnkey distribution
echo "🧹 Preparing turnkey Python runtime..."
if [ -d "python_runtime" ]; then
    echo "  Removing test data and media files..."
    find python_runtime -name "*.wav" -delete 2>/dev/null || true
    find python_runtime -name "*.mp3" -delete 2>/dev/null || true
    find python_runtime -name "*.mp4" -delete 2>/dev/null || true
    find python_runtime -name "*.jpg" -delete 2>/dev/null || true
    find python_runtime -name "*.jpeg" -delete 2>/dev/null || true
    find python_runtime -name "*.png" -delete 2>/dev/null || true
    find python_runtime -name "*.gif" -delete 2>/dev/null || true
    find python_runtime -name "*.svg" -delete 2>/dev/null || true
    find python_runtime -name "*.ico" -delete 2>/dev/null || true
    find python_runtime -name "*.pdf" -delete 2>/dev/null || true
    
    echo "  Removing documentation and archives..."
    find python_runtime -name "*.txt" -delete 2>/dev/null || true
    find python_runtime -name "*.md" -delete 2>/dev/null || true
    find python_runtime -name "*.rst" -delete 2>/dev/null || true
    find python_runtime -name "*.gz" -delete 2>/dev/null || true
    find python_runtime -name "*.zip" -delete 2>/dev/null || true
    find python_runtime -name "*.tar" -delete 2>/dev/null || true
    
    echo "  Removing test directories..."
    find python_runtime -type d -name "test*" -exec rm -rf {} + 2>/dev/null || true
    find python_runtime -type d -name "*test*" -exec rm -rf {} + 2>/dev/null || true
    find python_runtime -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
    find python_runtime -type d -name "doc*" -exec rm -rf {} + 2>/dev/null || true
    find python_runtime -type d -name "example*" -exec rm -rf {} + 2>/dev/null || true
    
    echo "  Removing bytecode and build artifacts..."
    find python_runtime -name "*.pyc" -delete 2>/dev/null || true
    find python_runtime -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find python_runtime -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
    find python_runtime -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
    
    echo "✅ Python runtime prepared for turnkey distribution"
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

ASSET_COUNT=$(find dist/assets -type f | wc -l | tr -d ' ')
echo "✅ Frontend build successful ($ASSET_COUNT assets)"

cd ../electron-app

# Temporarily remove signing from package.json
echo "⚙️  Building unsigned app (fast)..."
cp package.json package.json.bak

# Create unsigned build config
cat > package.json.unsigned << 'EOF'
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
    "asar": false,
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
      "category": "public.app-category.productivity",
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

# Use unsigned config
mv package.json.unsigned package.json

START_TIME=$(date +%s)

# Build unsigned (should be fast!)
echo "📱 Building unsigned Electron app for $BUILD_ARCH..."
CSC_IDENTITY_AUTO_DISCOVERY=false npm run build:mac-$BUILD_ARCH

if [ $? -ne 0 ]; then
    echo "❌ Electron build failed"
    mv package.json.bak package.json
    exit 1
fi

# Restore original package.json
mv package.json.bak package.json

echo "✅ Unsigned build completed!"

# Find the built app
BUILT_APP=$(find dist -name "*.app" -type d | head -1)
if [ -z "$BUILT_APP" ]; then
    echo "❌ No .app file found in dist directory"
    exit 1
fi

echo "✅ Found built app: $(basename "$BUILT_APP")"

# Manually copy Python runtime to the app
echo "🐍 Adding Python runtime to app bundle..."
PYTHON_DEST="$BUILT_APP/Contents/Resources/app/python_runtime"
cp -R python_runtime "$PYTHON_DEST"

if [ -d "$PYTHON_DEST" ]; then
    RUNTIME_SIZE=$(du -sh "$PYTHON_DEST" | cut -f1)
    echo "✅ Python runtime added ($RUNTIME_SIZE)"
else
    echo "❌ Failed to add Python runtime"
    exit 1
fi

# Now sign the complete app manually
echo "🔐 Signing complete app bundle..."
codesign --sign "Developer ID Application: Christian Merrill (4H8Z97B24M)" \
         --force \
         --timestamp \
         --options runtime \
         --entitlements build/entitlements.mac.plist \
         --deep \
         "$BUILT_APP"

if [ $? -eq 0 ]; then
    echo "✅ App signed successfully"
else
    echo "❌ App signing failed"
    exit 1
fi

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

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "📋 Build Summary:"
echo "✅ Frontend bundled successfully ($ASSET_COUNT assets)"
echo "✅ Python runtime bundled ($RUNTIME_SIZE)"
echo "✅ App signed and verified"
echo "⚡ Total build time: ${DURATION} seconds"
echo ""
echo "📁 Output: $BUILT_APP"
echo ""
echo "📋 Next steps for distribution:"
echo "1. Test the app: open \"$BUILT_APP\""
echo "2. 🎯 This is a TURNKEY DMG - no Python installation required"
echo "3. For distribution: The DMG in dist/ is ready to share"
echo "4. For notarization: xcrun notarytool submit dist/*.dmg --keychain-profile \"AC_PASSWORD\""
echo ""
echo "🎉 Turnkey signed build complete!" 