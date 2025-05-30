#!/bin/bash

# Fix script for Theseus Insight distributed app
# This script fixes common issues when running the app on other Macs

set -e

echo "🔧 Theseus Insight App Fix Script"
echo "================================="
echo ""

APP_PATH="/Applications/Theseus Insight.app"

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    echo "❌ Theseus Insight.app not found in /Applications/"
    echo "   Please drag the app to /Applications first"
    exit 1
fi

echo "✅ Found app at: $APP_PATH"
echo ""

# Fix 1: Remove quarantine attributes
echo "🔒 Removing quarantine attributes..."
if xattr -r -d com.apple.quarantine "$APP_PATH" 2>/dev/null; then
    echo "✅ Quarantine attributes removed"
else
    echo "ℹ️  No quarantine attributes found (or already removed)"
fi

# Fix 2: Clear other problematic attributes
echo "🔒 Clearing extended attributes..."
xattr -cr "$APP_PATH" 2>/dev/null || true
echo "✅ Extended attributes cleared"

# Fix 3: Set proper permissions
echo "🔧 Setting proper permissions..."
chmod -R 755 "$APP_PATH"
chmod +x "$APP_PATH/Contents/MacOS/Theseus Insight"
echo "✅ Permissions set"

# Fix 4: Clear any cached signature info
echo "🔧 Clearing signature cache..."
sudo spctl --master-disable 2>/dev/null || true
sudo spctl --master-enable 2>/dev/null || true
echo "✅ Signature cache cleared"

echo ""
echo "🎉 App fixes applied successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Try launching the app normally (double-click)"
echo "2. If prompted about security, click 'Open'"
echo "3. The app should now start properly"
echo ""

# Test launch
echo "🚀 Testing app launch..."
echo "   (This will attempt to start the app and show any errors)"

# Try to launch and capture any immediate errors
if ! open "$APP_PATH" 2>&1; then
    echo "❌ App failed to launch"
    echo "   Check Console.app for crash logs"
else
    echo "✅ App launched successfully"
    echo "   If you see a blank screen, wait a moment for the backend to start"
fi 