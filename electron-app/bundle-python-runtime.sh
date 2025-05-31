#!/bin/bash

# Bundle a standalone Python runtime with required dependencies for Theseus Insight
# Creates a local virtual environment under electron-app/python_runtime
# This allows the packaged Electron application to run without system Python

set -e

RUNTIME_DIR="python_runtime"

# Remove old runtime
rm -rf "$RUNTIME_DIR"

# Create virtual environment
python3 -m venv "$RUNTIME_DIR"

# Upgrade pip inside the venv
"$RUNTIME_DIR/bin/pip" install --upgrade pip >/dev/null

# Install all requirements from requirements.txt
echo "Installing dependencies from requirements.txt..."
"$RUNTIME_DIR/bin/pip" install -r ../requirements.txt >/dev/null

echo "✅ Python runtime bundled in $RUNTIME_DIR"
