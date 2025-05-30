#!/bin/bash

# Comprehensive build script for Theseus Insight Electron App
set -e  # Exit on any error

echo "🚀 Starting Theseus Insight Electron App Build Process..."

# Check if we're in the correct directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Run this script from the electron-app directory"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command_exists npm; then
    echo "❌ Error: npm is not installed"
    exit 1
fi

if ! command_exists node; then
    echo "❌ Error: Node.js is not installed"
    exit 1
fi

echo "✅ Prerequisites check passed"

# Step 1: Fix PostgreSQL paths for portability
echo "🔧 Fixing PostgreSQL paths for distribution..."

if [ -d "postgres/darwin" ]; then
    BIN_DIR="postgres/darwin/bin"
    LIB_DIR="postgres/darwin/lib"
    
    if [ -d "$BIN_DIR" ] && [ -d "$LIB_DIR" ]; then
        echo "📁 Found PostgreSQL binaries, fixing hardcoded paths..."
        
        # Function to fix a single binary
        fix_binary() {
            local binary_path="$1"
            local binary_name=$(basename "$binary_path")
            
            # Get current library dependencies with hardcoded paths
            local old_paths=$(otool -L "$binary_path" 2>/dev/null | grep "/Users/c/software_projects" | awk '{print $1}' || true)
            
            if [ -n "$old_paths" ]; then
                echo "   🔄 Fixing: $binary_name"
                # Fix each hardcoded path
                while IFS= read -r old_path; do
                    if [ -n "$old_path" ]; then
                        local lib_name=$(basename "$old_path")
                        local new_path="@loader_path/../lib/$lib_name"
                        
                        install_name_tool -change "$old_path" "$new_path" "$binary_path" 2>/dev/null || {
                            echo "   ⚠️  Failed to update $lib_name in $binary_name"
                        }
                    fi
                done <<< "$old_paths"
            fi
        }
        
        # Function to fix library internal IDs
        fix_library() {
            local lib_path="$1"
            local lib_name=$(basename "$lib_path")
            
            # Get current library ID
            local current_id=$(otool -D "$lib_path" 2>/dev/null | sed -n '2p' | xargs || true)
            
            if [[ "$current_id" == *"/Users/c/software_projects"* ]]; then
                local new_id="@loader_path/$lib_name"
                install_name_tool -id "$new_id" "$lib_path" 2>/dev/null || {
                    echo "   ⚠️  Failed to update library ID for $lib_name"
                }
            fi
            
            # Fix dependencies within the library
            fix_binary "$lib_path"
        }
        
        # Fix library IDs first
        for lib in "$LIB_DIR"/*.dylib; do
            if [ -f "$lib" ]; then
                fix_library "$lib"
            fi
        done
        
        # Fix binary dependencies
        for binary in "$BIN_DIR"/*; do
            if [ -f "$binary" ] && [ -x "$binary" ]; then
                # Skip shell scripts
                if ! file "$binary" | grep -q "shell script"; then
                    fix_binary "$binary"
                fi
            fi
        done
        
        echo "✅ PostgreSQL paths fixed for distribution"
    else
        echo "⚠️  PostgreSQL bin/lib directories not found, skipping path fixing"
    fi
else
    echo "⚠️  No PostgreSQL directory found, skipping path fixing"
fi

# Step 2: Build the UI
echo "🎨 Building React UI..."
cd ../theseus-ui

if [ ! -f "package.json" ]; then
    echo "❌ Error: theseus-ui directory not found or invalid"
    exit 1
fi

# Install UI dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing UI dependencies..."
    npm install
fi

# Build the UI
echo "🔨 Building UI for production..."
npm run build

# Check if build was successful
if [ ! -d "dist" ]; then
    echo "❌ Error: UI build failed - dist directory not found"
    exit 1
fi

echo "✅ UI build completed successfully"

# Step 3: Verify config files
echo "📋 Verifying configuration files..."
cd ../

CONFIG_FILES=("config/orchestration.json" "config/research_interests.txt" "config/arxiv_taxonomy.json")
for file in "${CONFIG_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "⚠️  Warning: Config file $file not found"
    else
        echo "✅ Found: $file"
    fi
done

# Step 4: Build Electron app
echo "⚡ Building Electron application..."
cd electron-app

# Install Electron dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Electron dependencies..."
    npm install
fi

# Determine build target
BUILD_TARGET=""
case "$1" in
    "mac"|"darwin")
        BUILD_TARGET="build:mac"
        echo "🍎 Building for macOS..."
        ;;
    "win"|"windows")
        BUILD_TARGET="build:win"
        echo "🪟 Building for Windows..."
        ;;
    "linux")
        BUILD_TARGET="build:linux"
        echo "🐧 Building for Linux..."
        ;;
    "")
        BUILD_TARGET="build"
        echo "🔧 Building for current platform..."
        ;;
    *)
        echo "❌ Error: Unknown build target '$1'"
        echo "Usage: $0 [mac|win|linux]"
        exit 1
        ;;
esac

# Run the build
npm run $BUILD_TARGET

# Check if build was successful
if [ $? -eq 0 ]; then
    echo "🎉 Build completed successfully!"
    echo "📁 Output files are in the 'dist' directory"
    
    # Verification step
    echo "🔍 Verifying PostgreSQL path fixes..."
    BUILT_APPS=(dist/*.app)
    if [ -f "${BUILT_APPS[0]}/Contents/Resources/app/postgres/darwin/bin/initdb" ]; then
        BUILT_BINARY="${BUILT_APPS[0]}/Contents/Resources/app/postgres/darwin/bin/initdb"
        BAD_PATHS=$(otool -L "$BUILT_BINARY" 2>/dev/null | grep "/Users/c/software_projects" || true)
        if [ -z "$BAD_PATHS" ]; then
            echo "✅ Verification passed: No hardcoded paths in built app"
        else
            echo "❌ Warning: Built app still contains hardcoded paths:"
            echo "$BAD_PATHS"
        fi
    else
        echo "⚠️  Could not verify paths (binary not found in expected location)"
    fi

    if [ -d "dist" ]; then
        echo ""
        echo "📋 Built files:"
        ls -la dist/ | grep -E "\.(dmg|app)$"
    fi
    
    echo ""
    echo "🚀 Ready for distribution!"
    echo "   The DMG should now work on other Macs without additional steps."
else
    echo "❌ Build failed!"
    exit 1
fi 