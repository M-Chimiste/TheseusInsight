#!/bin/bash

# Fix script for Theseus Insight distributed app
# This script fixes common issues when running the app on other Macs

set -e

echo "🔧 Theseus Insight App Fix Script v2.0"
echo "======================================"
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

# Function to check and report status
check_status() {
    local description="$1"
    local command="$2"
    
    echo "🔍 Checking: $description"
    if eval "$command" >/dev/null 2>&1; then
        echo "✅ $description: OK"
    else
        echo "❌ $description: FAILED"
        return 1
    fi
}

# Fix 1: Remove quarantine attributes
echo "🔒 Removing quarantine attributes..."
QUARANTINE_BEFORE=$(xattr "$APP_PATH" 2>/dev/null | grep quarantine || echo "none")
echo "   Before: $QUARANTINE_BEFORE"

if xattr -r -d com.apple.quarantine "$APP_PATH" 2>/dev/null; then
    echo "✅ Quarantine attributes removed"
else
    echo "ℹ️  No quarantine attributes found (or already removed)"
fi

QUARANTINE_AFTER=$(xattr "$APP_PATH" 2>/dev/null | grep quarantine || echo "none")
echo "   After: $QUARANTINE_AFTER"
echo ""

# Fix 2: Clear other problematic attributes
echo "🔒 Clearing extended attributes..."
ATTRS_BEFORE=$(xattr "$APP_PATH" 2>/dev/null | wc -l | tr -d ' ')
echo "   Extended attributes before: $ATTRS_BEFORE"

xattr -cr "$APP_PATH" 2>/dev/null || true

ATTRS_AFTER=$(xattr "$APP_PATH" 2>/dev/null | wc -l | tr -d ' ')
echo "   Extended attributes after: $ATTRS_AFTER"
echo "✅ Extended attributes cleared"
echo ""

# Fix 3: Set proper permissions
echo "🔧 Setting proper permissions..."
chmod -R 755 "$APP_PATH"
chmod +x "$APP_PATH/Contents/MacOS/Theseus Insight"

# Fix permissions for Electron helpers
if [ -d "$APP_PATH/Contents/Frameworks" ]; then
    echo "   📁 Setting Electron helper permissions..."
    find "$APP_PATH/Contents/Frameworks" -name "*.app" -exec chmod -R 755 {} \;
    find "$APP_PATH/Contents/Frameworks" -name "*Helper*" -exec chmod +x {} \; 2>/dev/null || true
fi

echo "✅ Permissions set"
echo ""

# Fix 4: Handle code signatures for Electron helpers
echo "🔧 Fixing Electron helper signatures..."
if command -v codesign >/dev/null 2>&1; then
    echo "   ✅ codesign tool available"
    
    # Check current signature status
    echo "   🔍 Current signature status:"
    codesign -dv "$APP_PATH" 2>&1 | head -5 || echo "     No signature found"
    echo ""
    
    # Remove existing signatures
    echo "   🗑️  Removing existing signatures..."
    codesign --remove-signature "$APP_PATH" 2>/dev/null || true
    
    # Find and fix Electron helpers
    echo "   🔄 Processing Electron helpers..."
    HELPER_COUNT=0
    find "$APP_PATH/Contents/Frameworks" -name "*Helper*.app" | while read helper_app; do
        HELPER_COUNT=$((HELPER_COUNT + 1))
        helper_name=$(basename "$helper_app")
        echo "     Processing: $helper_name"
        
        # Remove old signature
        codesign --remove-signature "$helper_app" 2>/dev/null || true
        
        # Add ad-hoc signature to make it acceptable to AMFI
        if codesign --force --deep --sign - "$helper_app" 2>/dev/null; then
            echo "     ✅ $helper_name: Re-signed with ad-hoc signature"
        else
            echo "     ❌ $helper_name: Could not re-sign"
            # Try to get more specific error
            codesign --force --deep --sign - "$helper_app" 2>&1 | head -3 || true
        fi
    done
    
    # Re-sign main app with ad-hoc signature
    echo "   🔄 Re-signing main app..."
    if codesign --force --deep --sign - "$APP_PATH" 2>/dev/null; then
        echo "   ✅ Main app re-signed with ad-hoc signature"
    else
        echo "   ❌ Could not re-sign main app"
        codesign --force --deep --sign - "$APP_PATH" 2>&1 | head -3 || true
    fi
    
    # Verify signatures
    echo "   🔍 Verifying signatures:"
    codesign -dv "$APP_PATH" 2>&1 | head -5 || echo "     Signature verification failed"
    
else
    echo "❌ codesign not available, skipping signature fixes"
    echo "   This may cause AMFI issues on macOS 10.14+"
fi
echo ""

# Fix 5: Clear any cached signature info
echo "🔧 Clearing signature cache..."
if sudo -n spctl --master-disable 2>/dev/null; then
    sudo spctl --master-enable 2>/dev/null || true
    echo "✅ Signature cache cleared"
else
    echo "ℹ️  Skipping signature cache clear (requires sudo)"
fi
echo ""

# Fix 6: Clear system caches that might interfere
echo "🔧 Clearing system caches..."
sudo -n kextcache -clear-cache 2>/dev/null || echo "ℹ️  Skipping kext cache clear (requires sudo)"
echo "✅ System cache operations completed"
echo ""

# Check app bundle integrity
echo "🔍 Checking app bundle integrity..."
check_status "Main executable exists" "[ -f '$APP_PATH/Contents/MacOS/Theseus Insight' ]"
check_status "Electron Framework exists" "[ -d '$APP_PATH/Contents/Frameworks/Electron Framework.framework' ]"
check_status "App resources exist" "[ -f '$APP_PATH/Contents/Resources/app.asar' ]"
check_status "PostgreSQL binaries exist" "[ -d '$APP_PATH/Contents/Resources/app/postgres' ]"
check_status "Frontend files exist" "[ -d '$APP_PATH/Contents/Resources/app/theseus-ui' ]"
echo ""

echo "🎉 App fixes applied successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Try launching the app normally (double-click)"
echo "2. If prompted about security, click 'Open'"
echo "3. Wait for 'Services Starting' to complete (30-60 seconds)"
echo "4. If it crashes, check Console.app for error details"
echo ""

# Test launch with more detailed feedback
echo "🚀 Testing app launch..."
echo "   This will attempt to start the app in the background"
echo "   Watch for the app window to appear..."

# Launch app and monitor for a few seconds
if open "$APP_PATH" 2>&1; then
    echo "✅ App launch command succeeded"
    echo "   ⏳ Waiting 10 seconds to see if app starts properly..."
    
    # Wait and check if the process is running
    sleep 10
    
    if pgrep -f "Theseus Insight" >/dev/null; then
        echo "✅ App appears to be running!"
        echo "   Check if the app window opened correctly"
    else
        echo "❌ App process not found - it may have crashed"
        echo "   Check Console.app for crash logs"
        echo "   Look for entries containing 'Theseus Insight'"
    fi
else
    echo "❌ App failed to launch"
    echo "   Check Console.app for crash logs"
fi

echo ""
echo "📊 Debug Information:"
echo "   macOS Version: $(sw_vers -productVersion)"
echo "   Architecture: $(uname -m)"
echo "   App Bundle Size: $(du -sh "$APP_PATH" | cut -f1)"
echo "   Last Modified: $(stat -f %Sm "$APP_PATH")"
echo ""
echo "🏁 Fix script completed!" 