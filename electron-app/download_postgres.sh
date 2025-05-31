#!/usr/bin/env bash
# Build and install pgvector extension into existing PostgreSQL binaries.
set -euo pipefail

PLATFORM="$(uname | tr 'A-Z' 'a-z')"
TARGET_DIR="$(dirname "$0")/postgres/${PLATFORM}"

echo "Installing pgvector extension for $PLATFORM..."

# Check if the target directory exists
if [[ ! -d "$TARGET_DIR" ]]; then
    echo "❌ PostgreSQL directory not found: $TARGET_DIR"
    echo "Please ensure PostgreSQL binaries are extracted to this location first."
    exit 1
fi

# Check if pg_config exists
if [[ ! -f "$TARGET_DIR/bin/pg_config" ]]; then
    echo "❌ pg_config not found in $TARGET_DIR/bin/"
    echo "Please ensure PostgreSQL is properly installed."
    exit 1
fi

echo "✅ PostgreSQL installation found in $TARGET_DIR"

#
# ---- Build and install pgvector extension ----
#
# pgvector provides the required VECTOR data type for similarity search.
#
if [[ "$PLATFORM" != msys* && "$PLATFORM" != mingw* && "$PLATFORM" != cygwin* && "$PLATFORM" != win32 ]]; then
    echo "Building and installing pgvector from source..."
    
    # Get absolute path to pg_config before changing directories
    PG_CONFIG_PATH="$(realpath "$TARGET_DIR/bin/pg_config")"
    
    # Set up proper SDK paths for macOS
    if [[ "$PLATFORM" == "darwin" ]]; then
        # Find the correct SDK
        CORRECT_SDK=""
        if [[ -d "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk" ]]; then
            CORRECT_SDK="/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk"
        elif [[ -d "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk" ]]; then
            CORRECT_SDK="/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk"
        fi
        
        if [[ -n "$CORRECT_SDK" ]]; then
            echo "Using SDK: $CORRECT_SDK"
            
            # Create a temporary directory for our wrapper pg_config
            TEMP_BIN_DIR="$(mktemp -d)"
            
            # Create a wrapper pg_config that fixes the SDK paths
            cat > "$TEMP_BIN_DIR/pg_config" << EOF
#!/bin/bash
# Wrapper pg_config that fixes hardcoded SDK paths
ORIGINAL_OUTPUT=\$("$PG_CONFIG_PATH" "\$@")
# Replace the hardcoded SDK path with the correct one
echo "\$ORIGINAL_OUTPUT" | sed 's|-isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX[0-9.]*\.sdk|-isysroot $CORRECT_SDK|g'
EOF
            chmod +x "$TEMP_BIN_DIR/pg_config"
            
            # Use our wrapper pg_config
            PG_CONFIG_PATH="$TEMP_BIN_DIR/pg_config"
        else
            echo "⚠️  Could not find macOS SDK, proceeding anyway..."
        fi
    fi
    
    # Create temporary directory for pgvector source
    PGVECTOR_SRC="$(mktemp -d)"
    
    echo "Cloning pgvector repository..."
    git clone --depth 1 https://github.com/pgvector/pgvector.git "$PGVECTOR_SRC"
    
    cd "$PGVECTOR_SRC"
    
    echo "Building pgvector..."
    # Use OPTFLAGS="" to disable problematic optimization flags
    make PG_CONFIG="$PG_CONFIG_PATH" OPTFLAGS=""
    
    echo "Installing pgvector..."
    make PG_CONFIG="$PG_CONFIG_PATH" OPTFLAGS="" install
    
    # Return to original directory
    cd - >/dev/null
    
    # Clean up temporary directories
    rm -rf "$PGVECTOR_SRC"
    if [[ -n "${TEMP_BIN_DIR:-}" ]]; then
        rm -rf "$TEMP_BIN_DIR"
    fi
    
    # Verify installation
    if [[ -f "$TARGET_DIR/lib/vector.so" && -f "$TARGET_DIR/share/extension/vector.control" ]]; then
        echo "✅ pgvector successfully installed into $TARGET_DIR"
    else
        echo "⚠️  pgvector installation may be incomplete. Checking for files..."
        echo "   Library: $(ls -la "$TARGET_DIR/lib/vector"* 2>/dev/null || echo "not found")"
        echo "   Extension: $(ls -la "$TARGET_DIR/share/extension/vector"* 2>/dev/null || echo "not found")"
    fi
else
    echo "❌ Windows platform detected"
    echo "pgvector build is not supported on Windows platforms in this script."
    echo "Please install pgvector manually from: https://github.com/pgvector/pgvector"
    exit 1
fi

echo ""
echo "🎉 pgvector installation complete!"
echo "You can now use the VECTOR data type in your PostgreSQL database."
