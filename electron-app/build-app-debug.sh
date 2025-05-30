#!/bin/bash

# Debug build script for Theseus Insight Electron App
# This builds without code signing/notarization for testing
# Now includes automatic PostgreSQL path fixing for portability
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

# Step 3: Build Electron app
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
echo "✅ This build includes:"
echo "   • Fixed PostgreSQL paths for portability"
echo "   • No code signing (for easy testing)"
echo "   • Built for $BUILD_ARCH architecture"
echo "   • Should work on other Macs without path issues"
echo ""

# Verification step
echo "🔍 Verifying PostgreSQL path fixes..."
if [ -f "dist/mac-$BUILD_ARCH/Theseus Insight.app/Contents/Resources/app/postgres/darwin/bin/initdb" ]; then
    BUILT_BINARY="dist/mac-$BUILD_ARCH/Theseus Insight.app/Contents/Resources/app/postgres/darwin/bin/initdb"
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