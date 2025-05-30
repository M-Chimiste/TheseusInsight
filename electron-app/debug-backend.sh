#!/bin/bash

# Backend debugging script for Theseus Insight
# This script helps diagnose backend startup issues

echo "🔍 Theseus Insight Backend Debugger"
echo "===================================="
echo ""

APP_PATH="/Applications/Theseus Insight.app"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ Theseus Insight.app not found in /Applications/"
    exit 1
fi

echo "📁 App found at: $APP_PATH"
echo ""

# Check critical backend components
echo "🔍 Checking backend components..."

PYTHON_PATH="$APP_PATH/Contents/Resources/app/run_theseus_insight.py"
REQUIREMENTS_PATH="$APP_PATH/Contents/Resources/app/requirements.txt"
THESEUS_PATH="$APP_PATH/Contents/Resources/app/theseus_insight"
POSTGRES_PATH="$APP_PATH/Contents/Resources/app/postgres"
FRONTEND_PATH="$APP_PATH/Contents/Resources/app/theseus-ui/dist"

echo "  📄 Python entry point: $([ -f "$PYTHON_PATH" ] && echo "✅ Found" || echo "❌ Missing")"
echo "  📄 Requirements file: $([ -f "$REQUIREMENTS_PATH" ] && echo "✅ Found" || echo "❌ Missing")"
echo "  📁 Theseus backend: $([ -d "$THESEUS_PATH" ] && echo "✅ Found" || echo "❌ Missing")"
echo "  📁 PostgreSQL binaries: $([ -d "$POSTGRES_PATH" ] && echo "✅ Found" || echo "❌ Missing")"
echo "  📁 Frontend files: $([ -d "$FRONTEND_PATH" ] && echo "✅ Found" || echo "❌ Missing")"
echo ""

# Check PostgreSQL setup
if [ -d "$POSTGRES_PATH" ]; then
    echo "🔍 Checking PostgreSQL setup..."
    PG_BIN="$POSTGRES_PATH/darwin/bin"
    PG_LIB="$POSTGRES_PATH/darwin/lib"
    
    echo "  📁 PostgreSQL bin: $([ -d "$PG_BIN" ] && echo "✅ Found" || echo "❌ Missing")"
    echo "  📁 PostgreSQL lib: $([ -d "$PG_LIB" ] && echo "✅ Found" || echo "❌ Missing")"
    
    if [ -f "$PG_BIN/initdb" ]; then
        echo "  🔍 PostgreSQL binary dependencies:"
        otool -L "$PG_BIN/initdb" | head -5 | while read line; do
            if [[ "$line" == *"@loader_path"* ]]; then
                echo "    ✅ $line"
            elif [[ "$line" == *"/Users/"* ]] || [[ "$line" == *"TheseusInsight"* ]]; then
                echo "    ❌ $line (hardcoded path)"
            elif [[ "$line" == *".dylib"* ]]; then
                echo "    ✅ $line"
            fi
        done
    fi
    echo ""
fi

# Check Python environment
echo "🔍 Checking Python environment..."
SYSTEM_PYTHON=$(which python3 2>/dev/null || echo "not found")
echo "  🐍 System Python: $SYSTEM_PYTHON"

if [ -f "$SYSTEM_PYTHON" ]; then
    PYTHON_VERSION=$($SYSTEM_PYTHON --version 2>&1)
    echo "  📊 Python version: $PYTHON_VERSION"
else
    echo "  ❌ Python3 not found in PATH"
fi
echo ""

# Check if app is currently running
echo "🔍 Checking if app is running..."
if pgrep -f "Theseus Insight" >/dev/null; then
    echo "  ✅ App process found:"
    ps aux | grep "Theseus Insight" | grep -v grep | while read line; do
        echo "    $line"
    done
    
    # Check if backend port is listening
    echo "  🔍 Checking backend port (8000):"
    if lsof -i :8000 >/dev/null 2>&1; then
        echo "    ✅ Port 8000 is in use (backend likely running)"
        lsof -i :8000 | grep LISTEN
    else
        echo "    ❌ Port 8000 not in use (backend not started)"
    fi
else
    echo "  ❌ App process not found"
fi
echo ""

# Try to launch app manually with detailed output
echo "🚀 Manual launch test..."
echo "  This will try to run the app from terminal to see error messages"
echo ""

# Launch app in background and monitor
echo "  ⏳ Launching app..."
open "$APP_PATH" &
APP_PID=$!

echo "  ⏳ Waiting 15 seconds for startup..."
sleep 15

# Check if it's running
if pgrep -f "Theseus Insight" >/dev/null; then
    echo "  ✅ App is running!"
    
    # Check backend
    if lsof -i :8000 >/dev/null 2>&1; then
        echo "  ✅ Backend appears to be running on port 8000"
    else
        echo "  ❌ Backend not detected on port 8000"
        echo "     This suggests a backend startup failure"
    fi
else
    echo "  ❌ App crashed or failed to start"
fi

echo ""
echo "📋 Recent crash reports:"
CRASH_DIR="$HOME/Library/Logs/DiagnosticReports"
if [ -d "$CRASH_DIR" ]; then
    find "$CRASH_DIR" -name "*Theseus*" -mtime -1 | head -3 | while read crash_file; do
        echo "  📄 $(basename "$crash_file")"
        echo "     Created: $(stat -f %Sm "$crash_file")"
    done
    
    if [ $(find "$CRASH_DIR" -name "*Theseus*" -mtime -1 | wc -l) -eq 0 ]; then
        echo "  ✅ No recent crash reports found"
    fi
else
    echo "  ❌ Crash reports directory not found"
fi

echo ""
echo "📊 System Information:"
echo "  💻 macOS Version: $(sw_vers -productVersion)"
echo "  🏗️  Architecture: $(uname -m)"
echo "  💾 Available RAM: $(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024) " GB"}')"
echo "  💿 Available Disk: $(df -h / | tail -1 | awk '{print $4}') free"

echo ""
echo "🏁 Backend debug complete!"
echo ""
echo "📧 Next steps:"
echo "1. If the app crashes immediately, check Console.app for AMFI errors"
echo "2. If the app starts but backend fails, check Console.app for Python/FastAPI errors"
echo "3. If backend starts but UI is blank, check network connectivity to localhost:8000"
echo "4. Share this output with the developer for further assistance" 