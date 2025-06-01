#!/bin/bash

# Bundle a completely standalone Python runtime for turnkey distribution
# Creates a self-contained Python installation with all dependencies

set -e

RUNTIME_DIR="python_runtime"

# Remove old runtime
rm -rf "$RUNTIME_DIR"

# Create virtual environment with copies instead of symlinks
python3 -m venv "$RUNTIME_DIR" --copies

# Find the actual Python executable in the venv
PYTHON_EXE="$RUNTIME_DIR/bin/python3"

# Upgrade pip inside the venv
"$PYTHON_EXE" -m pip install --upgrade pip >/dev/null

# Install all requirements from requirements.txt
echo "Installing dependencies from requirements.txt..."
"$PYTHON_EXE" -m pip install -r ../requirements.txt >/dev/null

# Make sure we have a working python3 executable (not a symlink)
if [ -L "$RUNTIME_DIR/bin/python3" ]; then
    # If it's still a symlink, copy the actual executable
    REAL_PYTHON=$(readlink "$RUNTIME_DIR/bin/python3")
    rm "$RUNTIME_DIR/bin/python3"
    cp "$REAL_PYTHON" "$RUNTIME_DIR/bin/python3"
fi

# Create a simple python symlink to python3
if [ ! -f "$RUNTIME_DIR/bin/python" ]; then
    ln -s python3 "$RUNTIME_DIR/bin/python"
fi

echo "✅ Standalone Python runtime bundled in $RUNTIME_DIR"
