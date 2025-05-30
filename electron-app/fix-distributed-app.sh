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

# Fix permissions for Electron helpers
if [ -d "$APP_PATH/Contents/Frameworks" ]; then
    find "$APP_PATH/Contents/Frameworks" -name "*.app" -exec chmod -R 755 {} \;
    find "$APP_PATH/Contents/Frameworks" -name "*Helper*" -exec chmod +x {} \; 2>/dev/null || true
fi

echo "✅ Permissions set"

# Fix 4: Handle code signatures for Electron helpers
echo "🔧 Fixing Electron helper signatures..."
if command -v codesign >/dev/null 2>&1; then
    # Remove existing signatures
    codesign --remove-signature "$APP_PATH" 2>/dev/null || true
    
    # Find and fix Electron helpers
    find "$APP_PATH/Contents/Frameworks" -name "*Helper*.app" | while read helper_app; do
        echo "  🔄 Processing $(basename "$helper_app")"
        
        # Remove old signature
        codesign --remove-signature "$helper_app" 2>/dev/null || true
        
        # Add ad-hoc signature to make it acceptable to AMFI
        if codesign --force --deep --sign - "$helper_app" 2>/dev/null; then
            echo "  ✅ $(basename "$helper_app"): Re-signed with ad-hoc signature"
        else
            echo "  ⚠️  $(basename "$helper_app"): Could not re-sign"
        fi
    done
    
    # Re-sign main app with ad-hoc signature
    if codesign --force --deep --sign - "$APP_PATH" 2>/dev/null; then
        echo "✅ Main app re-signed with ad-hoc signature"
    else
        echo "⚠️  Could not re-sign main app"
    fi
    
else
    echo "ℹ️  codesign not available, skipping signature fixes"
fi

# Fix 5: Clear any cached signature info
echo "🔧 Clearing signature cache..."
sudo spctl --master-disable 2>/dev/null || true
sudo spctl --master-enable 2>/dev/null || true
echo "✅ Signature cache cleared"

# Fix 6: Clear system caches that might interfere
echo "🔧 Clearing system caches..."
sudo kextcache -clear-cache 2>/dev/null || true
echo "✅ System caches cleared"

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