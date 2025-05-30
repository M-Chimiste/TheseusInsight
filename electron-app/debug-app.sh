#!/bin/bash

# Debug script for Theseus Insight app crashes
# Run this on the Mac where the app is failing to start

echo "🔍 Theseus Insight App Debug Script"
echo "=================================="
echo ""

# Check if app exists
APP_PATH="/Applications/Theseus Insight.app"
if [ ! -d "$APP_PATH" ]; then
    echo "❌ App not found at $APP_PATH"
    echo "Please check if the app is installed in Applications folder"
    exit 1
fi

echo "✅ App found at: $APP_PATH"
echo ""

# System Information
echo "🖥️  System Information:"
echo "OS Version: $(sw_vers -productVersion)"
echo "Architecture: $(uname -m)"
echo "Available RAM: $(sysctl hw.memsize | awk '{print $2/1024/1024/1024 " GB"}')"
echo ""

# Check Console logs for crashes
echo "📋 Checking Console logs for recent crashes..."
echo "Looking for crashes in the last 5 minutes..."

# Create a timestamp for 5 minutes ago
FIVE_MINS_AGO=$(date -v-5M '+%Y-%m-%d %H:%M:%S')

echo "Searching from: $FIVE_MINS_AGO"
echo ""

# Check for crash reports
echo "🔍 Crash Reports:"
find ~/Library/Logs/DiagnosticReports -name "*Theseus*" -newermt "$FIVE_MINS_AGO" 2>/dev/null | head -5 | while read -r file; do
    echo "Found: $file"
    echo "--- Last 20 lines ---"
    tail -20 "$file"
    echo ""
done

# Check system logs
echo "🔍 System Console Logs (last 50 lines mentioning Theseus):"
log show --predicate 'eventMessage contains "Theseus"' --last 5m 2>/dev/null | tail -50
echo ""

# Try to run the app from Terminal to see errors
echo "🚀 Attempting to run app from Terminal..."
echo "This may show error messages that aren't visible when double-clicking:"
echo ""

cd "$APP_PATH/Contents/MacOS"
echo "Running: $APP_PATH/Contents/MacOS/Theseus\ Insight"
echo "Output:"
echo "-------"

# Run the app and capture output
timeout 10s "./Theseus Insight" 2>&1 || echo "App exited or timed out"
echo ""

# Check for missing dependencies
echo "🔍 Checking for potential missing dependencies..."

# Check if Python is available
echo "Python check:"
if command -v python3 >/dev/null 2>&1; then
    echo "✅ Python3 found: $(python3 --version)"
else
    echo "❌ Python3 not found in PATH"
fi

# Check for common libraries
echo ""
echo "Library checks:"
otool -L "$APP_PATH/Contents/MacOS/Theseus Insight" 2>/dev/null | grep -E "(not found|@rpath)" || echo "✅ No obvious missing libraries"

echo ""
echo "🔍 App Bundle Contents:"
echo "Contents structure:"
ls -la "$APP_PATH/Contents/"
echo ""
echo "Resources structure:"
ls -la "$APP_PATH/Contents/Resources/" | head -10
echo ""

# Check file permissions
echo "🔍 File Permissions:"
ls -la "$APP_PATH/Contents/MacOS/Theseus Insight"
echo ""

# Check quarantine attributes
echo "🔍 Quarantine Attributes:"
xattr -l "$APP_PATH" 2>/dev/null || echo "No extended attributes found"
echo ""

# Check code signature
echo "🔍 Code Signature Status:"
codesign -v "$APP_PATH" 2>&1 || echo "No valid code signature"
echo ""

echo "🏁 Debug complete!"
echo ""
echo "📧 Please share this output with the developer."
echo "   Pay special attention to any error messages in the 'Terminal output' section." 